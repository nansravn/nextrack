#!/usr/bin/env python3
"""nextrack_tags.py — tidy & retag the DJ audio library.

The library is a folder tree of downloaded audio (mp3/flac), one subfolder per
genre-node id, mirroring this repo's `tracks/*.yml` pools. Filenames are meant to
read `Artist - Title.ext`. Two things drift over time: embedded tags (Title/Artist
often blank or garbage in downloaded MP3s) and stray junk in filenames
(`[NotSlider.nl]`, `vk.com`, trailing ` - Tech House`, `(infantil)`).

This tool fixes both — and harvests the BPM/key that Serato/Tidal already wrote
INTO the files back into the repo YAML.

It edits tags with `mutagen`, which rewrites only the tag block (no re-encode), so
Serato's beatgrids/cue GEOB frames survive. Never use ffmpeg to retag these files.

Everything is DRY-RUN by default. Pass --apply to actually write. Pilot on one
folder first with --only, e.g.  `fix-tags --only axe --apply`.

The library root comes from --root, or from $NEXTRACK_AUDIO_ROOT if unset.

Subcommands:
  audit        report parsed vs embedded Artist/Title, BPM/key, and flags (no writes)
  clean-names  strip junk from filenames -> `Artist - Title.ext`
  fix-tags     write Title/Artist embedded tags from the (clean) filename
  pull-bpm     read embedded BPM/key from files -> fill null bpm/key in tracks/*.yml

See scripts/README.md.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

try:
    from mutagen.id3 import ID3, TIT2, TPE1, ID3NoHeaderError
    from mutagen.flac import FLAC
except ImportError:
    sys.exit(
        "mutagen not installed.\n"
        "  Run:  sudo apt-get install -y python3-mutagen\n"
        "  Then: python3 -c \"import mutagen; print(mutagen.version)\""
    )

ROOT_ENV = "NEXTRACK_AUDIO_ROOT"  # machine-specific, so it lives outside the repo
AUDIO_EXTS = (".mp3", ".flac", ".wav")

# ------------------------------------------------------------------ filenames --
# Bracketed blocks that are download-site tags (contain a domain) -> junk.
JUNK_BRACKET = re.compile(
    r"\s*\[[^\]]*(?:notslider|www\.|\.nl|\.kz|\.ru|\.com)[^\]]*\]",
    re.I,
)
# A house-family genre label: an optional known qualifier + "house" (so "Slap
# House" / "Tech House" strip as one unit, not leaving an orphan "Slap").
_HOUSE = (r"(?:(?:slap|tech|deep|bass|future|progressive|electro|acid|tribal|"
          r"afro|melodic|jackin'?)\s+)?house")
# Trailing ` - <genre>` / ` - Música N` suffixes from download sites.
JUNK_SUFFIX = re.compile(rf"\s*-\s*(?:{_HOUSE}|m[uú]sica\s*\d+)\s*$", re.I)
# A dangling genre label left at the very end (after a bracket was removed).
JUNK_TRAIL_BARE = re.compile(rf"\s+(?:{_HOUSE})\s*$", re.I)
JUNK_INFANTIL = re.compile(r"\s*\(\s*infantil\s*\)", re.I)


def clean_stem(stem: str) -> str:
    """Return the filename stem with known junk removed. Semantic parens/brackets
    like `(... Remix)` or `[Salsa Version]` are kept."""
    s = stem
    s = JUNK_BRACKET.sub("", s)
    s = JUNK_INFANTIL.sub("", s)
    prev = None
    while prev != s:  # a name may carry more than one suffix
        prev = s
        s = JUNK_SUFFIX.sub("", s)
    s = JUNK_TRAIL_BARE.sub("", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    s = re.sub(r"\s+-\s*$", "", s).strip()  # dangling trailing dash
    return s


def parse_artist_title(stem: str) -> tuple[str | None, str]:
    """Split `Artist - Title` on the FIRST ' - ' (artist owns the first segment)."""
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return None, stem.strip()


def normalize(s: str | None) -> str:
    """Fold accents/case/punctuation for fuzzy YAML<->file matching."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------- key maps --
_MAJ = {
    "C": "8B", "C#": "3B", "Db": "3B", "D": "10B", "D#": "5B", "Eb": "5B",
    "E": "12B", "F": "7B", "F#": "2B", "Gb": "2B", "G": "9B", "G#": "4B",
    "Ab": "4B", "A": "11B", "A#": "6B", "Bb": "6B", "B": "1B",
}
_MIN = {
    "C": "5A", "C#": "12A", "Db": "12A", "D": "7A", "D#": "2A", "Eb": "2A",
    "E": "9A", "F": "4A", "F#": "11A", "Gb": "11A", "G": "6A", "G#": "1A",
    "Ab": "1A", "A": "8A", "A#": "3A", "Bb": "3A", "B": "10A",
}


def to_camelot(k: str | None) -> str | None:
    """Musical key ('Fm', 'B', 'Ebm') -> Camelot ('4A', '1B', '2A'). Passes an
    already-Camelot value through unchanged. Returns None if unrecognized."""
    if not k:
        return None
    k = k.strip()
    if re.fullmatch(r"\d{1,2}[ABab]", k):
        return k[:-1] + k[-1].upper()
    minor = k.endswith("m")
    root = (k[:-1] if minor else k).strip()
    if not root:
        return None
    root = root[0].upper() + root[1:]
    root = root.replace("♯", "#").replace("♭", "b")
    return (_MIN if minor else _MAJ).get(root)


def to_bpm(v) -> int | None:
    try:
        return round(float(str(v)))
    except (TypeError, ValueError):
        return None


# Placeholder artists some beat-pack / ripped files ship with — treat as missing.
PLACEHOLDER_ARTISTS = {"mix tutorial", "current song", "next song"}

# Generic version words — ignored when fuzzily matching a pool title to a file,
# so "(… Remix)" and "(… Extended Mix)" of the same track still line up.
VERSION_WORDS = {"remix", "extended", "mix", "edit", "version", "radio",
                 "original", "club", "vip", "rework", "bootleg", "ao", "vivo"}


def strip_sitejunk(v: str | None) -> str:
    """Remove download-site brackets (`[NotSlider.nl]`, `[vk.com…]`) from a tag."""
    return JUNK_BRACKET.sub("", v or "").strip()


def is_junk_title(v: str | None) -> bool:
    v = (v or "").strip()
    return (not v) or len(v) <= 2 or bool(re.search(r"(current|next)\s+song", v, re.I))


def is_junk_artist(v: str | None) -> bool:
    v = (v or "").strip()
    return (not v) or normalize(v) in PLACEHOLDER_ARTISTS


# ------------------------------------------------------------------- file I/O --
def iter_files(root: Path, only: str | None):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            rel = str(p.relative_to(root))
            if only and only.lower() not in rel.lower():
                continue
            yield p, rel


def read_embedded(p: Path) -> dict:
    """Return {title, artist, bpm, key} as currently embedded (best effort)."""
    ext = p.suffix.lower()
    out = {"title": None, "artist": None, "bpm": None, "key": None}
    try:
        if ext == ".mp3":
            try:
                tags = ID3(p)
            except ID3NoHeaderError:
                return out
            if tags.get("TIT2"):
                out["title"] = str(tags["TIT2"].text[0])
            if tags.get("TPE1"):
                out["artist"] = str(tags["TPE1"].text[0])
            if tags.get("TBPM"):
                out["bpm"] = to_bpm(tags["TBPM"].text[0])
            if tags.get("TKEY"):
                out["key"] = to_camelot(str(tags["TKEY"].text[0]))
        elif ext == ".flac":
            f = FLAC(p)
            out["title"] = (f.get("title") or [None])[0]
            out["artist"] = (f.get("artist") or [None])[0]
            out["bpm"] = to_bpm((f.get("bpm") or [None])[0])
            key = (f.get("initialkey") or f.get("key") or [None])[0]
            out["key"] = to_camelot(key)
    except Exception as e:  # noqa: BLE001 - report, never crash the batch
        out["error"] = str(e)
    return out


# --------------------------------------------------------------------- audit ---
def cmd_audit(args, root: Path):
    rows = []
    for p, rel in iter_files(root, args.only):
        stem = p.stem
        cleaned = clean_stem(stem)
        f_artist, f_title = parse_artist_title(cleaned)
        emb = read_embedded(p)
        flags = []
        if p.suffix.lower() == ".wav":
            flags.append("wav-skip")
        if not emb.get("title"):
            flags.append("missing-title")
        elif is_junk_title(emb["title"]):
            flags.append("garbage-title")
        if not emb.get("artist"):
            flags.append("missing-artist")
        if cleaned != stem:
            flags.append("junk-name")
        if " - " not in cleaned:
            flags.append("no-separator")
        if emb.get("title") and f_title and normalize(emb["title"]) != normalize(f_title):
            flags.append("title!=file")
        rows.append(
            {
                "path": rel,
                "file_artist": f_artist or "",
                "file_title": f_title,
                "emb_artist": emb.get("artist") or "",
                "emb_title": emb.get("title") or "",
                "bpm": emb.get("bpm") or "",
                "key": emb.get("key") or "",
                "flags": ",".join(flags),
            }
        )

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows -> {args.csv}")

    shown = rows if args.verbose else [r for r in rows if r["flags"]]
    for r in shown[: args.limit] if args.limit else shown:
        print(f"  {r['path']}")
        print(
            f"      file: {r['file_artist']!r} - {r['file_title']!r} | "
            f"emb: {r['emb_artist']!r} - {r['emb_title']!r} | "
            f"bpm={r['bpm']} key={r['key']}"
        )
        if r["flags"]:
            print(f"      FLAGS: {r['flags']}")

    # Summary
    c = Counter(f for r in rows for f in r["flags"].split(",") if f)
    print(f"\n=== {len(rows)} files "
          f"({'filtered by --only ' + args.only if args.only else 'whole library'}) ===")
    for flag, n in c.most_common():
        print(f"  {n:4d}  {flag}")


# ---------------------------------------------------------------- clean-names ---
def cmd_clean_names(args, root: Path):
    n_changed = n_skipped = 0
    log = []
    for p, rel in iter_files(root, args.only):
        cleaned = clean_stem(p.stem)
        if cleaned == p.stem:
            continue
        target = p.with_name(cleaned + p.suffix)
        if target.exists() and target != p:
            print(f"  SKIP (target exists): {rel} -> {target.name}")
            n_skipped += 1
            continue
        print(f"  {rel}\n      -> {target.name}")
        log.append((str(p), str(target)))
        if args.apply:
            p.rename(target)
        n_changed += 1
    verb = "renamed" if args.apply else "would rename"
    print(f"\n=== {verb} {n_changed}, skipped {n_skipped} ===")
    if args.apply and log:
        logpath = root / "_nextrack_rename_log.tsv"
        with open(logpath, "a", encoding="utf-8") as fh:
            for a, b in log:
                fh.write(f"{a}\t{b}\n")
        print(f"rename log appended -> {logpath}")


# ------------------------------------------------------------------- fix-tags ---
def _desired_tags(emb: dict, f_artist, f_title, yaml_hit, overwrite: bool):
    """Decide the Title/Artist to write. Default is CONSERVATIVE: keep a present,
    non-junk embedded value (just strip site-junk); only fall back to the filename
    (or a curated YAML entry) when the embedded value is missing or junk. This
    never trades a richer embedded artist (e.g. featured artists) for a poorer
    filename. --overwrite forces filename/YAML to win (use with care)."""
    y_title = yaml_hit["title"] if yaml_hit else None
    y_artist = yaml_hit["artist"] if yaml_hit else None

    ct = strip_sitejunk(emb.get("title"))
    ca = strip_sitejunk(emb.get("artist"))
    if overwrite:
        want_title = y_title or f_title
        want_artist = y_artist or f_artist
    else:
        want_title = ct if not is_junk_title(ct) else (y_title or f_title)
        want_artist = ca if not is_junk_artist(ca) else (y_artist or f_artist)
    return want_title, want_artist


def cmd_fix_tags(args, root: Path, yaml_index: dict | None):
    n_changed = n_ok = n_skip = 0
    for p, rel in iter_files(root, args.only):
        ext = p.suffix.lower()
        if ext == ".wav":
            print(f"  SKIP wav: {rel}")
            n_skip += 1
            continue
        f_artist, f_title = parse_artist_title(clean_stem(p.stem))
        yaml_hit = (yaml_index or {}).get((normalize(f_artist), normalize(f_title)))
        emb = read_embedded(p)
        want_title, want_artist = _desired_tags(
            emb, f_artist, f_title, yaml_hit, args.overwrite
        )

        changes = []
        if want_title and (emb.get("title") or "").strip() != want_title.strip():
            changes.append(("Title", "TIT2", emb.get("title"), want_title))
        if want_artist and (emb.get("artist") or "").strip() != want_artist.strip():
            changes.append(("Artist", "TPE1", emb.get("artist"), want_artist))
        if not changes:
            n_ok += 1
            continue

        print(f"  {rel}")
        for field, _, old, new in changes:
            print(f"      {field}: {old!r} -> {new!r}")
        n_changed += 1

        if not args.apply:
            continue
        if ext == ".mp3":
            try:
                tags = ID3(p)
            except ID3NoHeaderError:
                tags = ID3()
            for _, frame_id, _, new in changes:
                cls = TIT2 if frame_id == "TIT2" else TPE1
                tags.setall(frame_id, [cls(encoding=3, text=[new])])
            tags.save(p, v2_version=4)  # keep v2.4; leaves GEOB/Serato frames intact
        elif ext == ".flac":
            f = FLAC(p)
            for field, _, _, new in changes:
                f["title" if field == "Title" else "artist"] = [new]
            f.save()
    verb = "updated" if args.apply else "would update"
    print(f"\n=== {verb} {n_changed}, already-ok {n_ok}, skipped {n_skip} ===")


# ------------------------------------------------------------------- pull-bpm ---
_ENTRY_RE = re.compile(r"^-\s+title:\s*(.+?)\s*$")
_FIELD_RE = re.compile(r"^\s+(title|artist|bpm|key):\s*(.*?)\s*$")


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse_pool(path: Path) -> list[dict]:
    """Parse a tracks/*.yml pool into entries with the line indices of bpm/key."""
    lines = path.read_text(encoding="utf-8").splitlines()
    entries, cur = [], None
    for i, line in enumerate(lines):
        m = _ENTRY_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"title": _unquote(m.group(1)), "artist": None,
                   "bpm_line": None, "bpm_val": None, "key_line": None, "key_val": None}
            continue
        if cur is None:
            continue
        fm = _FIELD_RE.match(line)
        if not fm:
            continue
        field, val = fm.group(1), fm.group(2)
        if field == "artist":
            cur["artist"] = _unquote(val)
        elif field == "bpm":
            cur["bpm_line"], cur["bpm_val"] = i, val.strip()
        elif field == "key":
            cur["key_line"], cur["key_val"] = i, val.strip()
    if cur:
        entries.append(cur)
    return entries


def cmd_pull_bpm(args, root: Path, tracks_dir: Path):
    # index files: exact (artist,title), by title, plus title token-sets for fuzzy
    files = []
    for p, _ in iter_files(root, args.only):
        emb = read_embedded(p)
        if emb.get("bpm") is None and emb.get("key") is None:
            continue
        a, t = parse_artist_title(clean_stem(p.stem))
        na, nt = normalize(a), normalize(t)
        files.append({"na": na, "nt": nt, "at": set(na.split()),
                      "tc": set(nt.split()) - VERSION_WORDS, "emb": emb})
    by_pair = {(f["na"], f["nt"]): f["emb"] for f in files}
    by_title = defaultdict(list)
    for f in files:
        by_title[f["nt"]].append(f["emb"])

    def match(na, nt):
        """Exact (artist,title) -> unique title -> fuzzy: the file's artist is the
        pool artist plus maybe extra collaborators, and the title cores (minus
        version words) are subset-compatible. So pool 'Skank - Algo Parecido
        (Remix)' lines up with file 'Skank, Dubdogz, Bruno Be - Algo Parecido
        (Extended)', but a genuinely different version stays unmatched."""
        emb = by_pair.get((na, nt))
        if emb is not None:
            return emb
        cands = by_title.get(nt)
        if cands and len(cands) == 1:
            return cands[0]
        pa, pc = set(na.split()), set(nt.split()) - VERSION_WORDS
        if not pc:
            return None

        def score(f):  # lower = closer; artist + title-core token distance
            return len(f["at"] ^ pa) + len(f["tc"] ^ pc)

        subs = [f for f in files
                if pa <= f["at"] and (pc <= f["tc"] or f["tc"] <= pc)]
        if len(subs) == 1:
            return subs[0]["emb"]
        if len(subs) > 1:
            subs.sort(key=score)
            if score(subs[0]) < score(subs[1]):  # a single clear winner
                return subs[0]["emb"]
        return None

    total_edits = 0
    unmatched = []
    for pool in sorted(tracks_dir.glob("*.yml")):
        lines = pool.read_text(encoding="utf-8").splitlines(keepends=True)
        entries = parse_pool(pool)
        edits = []  # (line_idx, new_line)
        for e in entries:
            na, nt = normalize(e["artist"]), normalize(e["title"])
            emb = match(na, nt)
            if emb is None:
                if e["bpm_val"] == "null" or e["key_val"] == "null":
                    unmatched.append(f"{pool.name}: {e['artist']} - {e['title']}")
                continue
            if e["bpm_line"] is not None and e["bpm_val"] in ("null", "", "~") and emb.get("bpm"):
                idx = e["bpm_line"]
                edits.append((idx, re.sub(r"(bpm:\s*).*", rf"\g<1>{emb['bpm']}", lines[idx])))
            if e["key_line"] is not None and e["key_val"] in ("null", "", "~") and emb.get("key"):
                idx = e["key_line"]
                edits.append((idx, re.sub(r"(key:\s*).*", rf"\g<1>{emb['key']}", lines[idx])))

        if edits:
            print(f"  {pool.name}: {len(edits)} field(s)")
            for idx, newline in edits:
                print(f"      L{idx+1}: {lines[idx].rstrip()}  ->  {newline.rstrip()}")
                lines[idx] = newline if newline.endswith("\n") else newline + "\n"
            total_edits += len(edits)
            if args.apply:
                pool.write_text("".join(lines), encoding="utf-8")

    if unmatched and args.verbose:
        print("\n  unmatched YAML entries (still null, no file found):")
        for u in unmatched:
            print(f"      {u}")
    verb = "wrote" if args.apply else "would write"
    print(f"\n=== {verb} {total_edits} bpm/key value(s); "
          f"{len(unmatched)} null entries unmatched ===")


# ------------------------------------------------------------------- yaml idx ---
def build_yaml_index(tracks_dir: Path) -> dict:
    """(norm_artist, norm_title) -> {title, artist} from all pools, for fix-tags."""
    idx = {}
    for pool in tracks_dir.glob("*.yml"):
        for e in parse_pool(pool):
            if e["artist"] and e["title"]:
                idx[(normalize(e["artist"]), normalize(e["title"]))] = {
                    "title": e["title"], "artist": e["artist"]
                }
    return idx


# ----------------------------------------------------------------------- main ---
def main(argv=None):
    repo_tracks = Path(__file__).resolve().parent.parent / "tracks"

    # Common flags live on a parent parser attached to each subcommand, so they
    # can be typed AFTER the subcommand (the natural order), e.g.
    #   nextrack_tags.py fix-tags --only axe --apply
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=os.environ.get(ROOT_ENV),
                        help=f"audio library root (default: ${ROOT_ENV})")
    common.add_argument("--only",
                        help="only files whose path contains this substring (pilot)")
    common.add_argument("--apply", action="store_true",
                        help="write changes (default: dry-run)")
    common.add_argument("--verbose", "-v", action="store_true")
    # Subcommands that read/write the repo pools.
    pools = argparse.ArgumentParser(add_help=False)
    pools.add_argument("--tracks-dir", default=str(repo_tracks))

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", parents=[common], help="report tags/names, no writes")
    a.add_argument("--csv", help="also dump full report to this CSV path")
    a.add_argument("--limit", type=int, default=0, help="cap rows printed")

    sub.add_parser("clean-names", parents=[common], help="strip junk from filenames")

    ft = sub.add_parser("fix-tags", parents=[common, pools],
                        help="fill missing/junk Title/Artist (conservative)")
    ft.add_argument("--overwrite", action="store_true",
                    help="force filename/YAML to win even over a present, good tag "
                         "(default keeps present non-junk tags — e.g. featured artists)")
    ft.add_argument("--no-yaml", action="store_true",
                    help="don't consult curated YAML title/artist")

    sub.add_parser("pull-bpm", parents=[common, pools],
                   help="fill null bpm/key in tracks/*.yml from files")

    args = ap.parse_args(argv)
    if not args.root:
        sys.exit(f"no library root: pass --root PATH or set {ROOT_ENV} "
                 "(see scripts/README.md)")
    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"root not found: {root}")

    if args.cmd == "audit":
        cmd_audit(args, root)
    elif args.cmd == "clean-names":
        cmd_clean_names(args, root)
    elif args.cmd == "fix-tags":
        yaml_index = None if args.no_yaml else build_yaml_index(Path(args.tracks_dir))
        cmd_fix_tags(args, root, yaml_index)
    elif args.cmd == "pull-bpm":
        cmd_pull_bpm(args, root, Path(args.tracks_dir))


if __name__ == "__main__":
    main()
