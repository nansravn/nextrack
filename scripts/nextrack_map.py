#!/usr/bin/env python3
"""nextrack_map.py — the musical map of a track (lightshows/maps/<slug>.yml).

A map says, bar by bar, who plays in a track (vocals, kick, percussion, bass, other), where
its sections, drops and phrases are, and where the owner's hot cues sit. It is made from the
audio (separated with Demucs), the SoundSwitch script's tempo map and rekordbox's cues.

Folders come from options or environment variables, never from the code:
  --project / NEXTRACK_SOUNDSWITCH_PROJECT   the SoundSwitch project folder
  --root    / NEXTRACK_AUDIO_ROOT            the audio library
  --rekordbox / NEXTRACK_REKORDBOX_DIR       the folder that holds rekordbox's master.db
Audio, rekordbox and the SoundSwitch project are only read.

Subcommands:
  analyze  make the map of a track, or of every track of a rekordbox playlist; an existing
           map is kept unless it is stale (audio, script GUID or tempo changed) or --force
  cues     reread the hot cues from rekordbox into existing maps (no audio)
  show     print a map as text: per 64 bars, the cues, one line per voice, the sections
  timeline print the set timeline of a rekordbox playlist: transitions, arrivals, set clock
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
import re
import sys
from pathlib import Path

import yaml

import check_repo
import musical_map as mm
import set_timeline as stl
import soundswitch_format as ssf
from rekordbox_cues import ANALYSIS_HINT, RbTrack, open_rekordbox  # noqa: F401  (tests replace it)

PROJECT_ENV = "NEXTRACK_SOUNDSWITCH_PROJECT"
ROOT_ENV = "NEXTRACK_AUDIO_ROOT"
REKORDBOX_ENV = "NEXTRACK_REKORDBOX_DIR"
DEFAULT_REPO = Path(__file__).resolve().parent.parent
SEPARATOR_NAME = "htdemucs"
SECTION_LETTERS = {"intro": "i", "groove": "g", "break": "b", "build": "u", "drop": "d", "outro": "o"}
SHOW_BARS = 64
LABEL_WIDTH = 9


class Refused(Exception):
    """One track cannot be handled; the message is the reason."""


# --------------------------------------------------------------- separation ----


def demucs_separator(device: str | None):
    """A separator `(audio (n, 2) float32, sr) -> ({vocals, drums, bass, other}, sr)` that runs
    Demucs `htdemucs`. torch and demucs are imported on the first call; the model loads once."""
    if any(importlib.util.find_spec(m) is None for m in ("torch", "demucs")):
        raise SystemExit(ANALYSIS_HINT)
    state: dict = {}

    def separate(x, sr):
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model

        if not state:
            dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
            model = get_model(SEPARATOR_NAME)
            model.eval()
            model.to(dev)
            state.update(model=model, dev=dev)
        model, dev = state["model"], state["dev"]
        wav = torch.from_numpy(x.T.copy())
        if sr != model.samplerate:
            import julius

            wav = julius.resample_frac(wav, sr, model.samplerate)
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        with torch.no_grad():
            out = apply_model(model, wav[None], device=dev, progress=False)[0]
        out = out * ref.std() + ref.mean()
        stems = {name: out[i].cpu().numpy().T.copy() for i, name in enumerate(model.sources)}
        return stems, int(model.samplerate)

    return separate


def make_separator(device: str | None):
    """The separator `analyze` uses (tests replace this)."""
    return demucs_separator(device)


# ------------------------------------------------------------------ helpers ----


def _base(path: str) -> str:
    parts = [p for p in re.split(r"[\\/]", path) if p]
    return parts[-1] if parts else ""


def _label(artist: str, title: str) -> str:
    return f"{artist} — {title}"


def pool_track(repo: check_repo.Repo, ref: ssf.TrackRef) -> str:
    """The pool's `Artist — Title` for a SoundSwitch track, else Refused."""
    found: list[tuple[str, str]] = []
    for pool in repo.pools:
        for e in pool.entries:
            a, t = e.get("artist"), e.get("title")
            if isinstance(a, str) and isinstance(t, str) and check_repo.same_track(ref.artist, ref.title, a, t):
                found.append((a, t))
    found = list(dict.fromkeys(found))
    if len(found) > 1:
        exact = [f for f in found if check_repo.norm(f[1]) == check_repo.norm(ref.title)]
        if len(exact) == 1:
            found = exact
    if not found:
        raise Refused("add it to its pool first")
    if len(found) > 1:
        raise Refused("several pool tracks match, make the pool tell them apart: "
                      + "; ".join(_label(a, t) for a, t in found))
    return _label(*found[0])


def map_path(repo_root: Path, track: str) -> Path:
    return repo_root / "lightshows" / "maps" / f"{mm.slug(track)}.yml"


def read_audio(raw: bytes):
    """`(samples (n, 2) float32, sr)` of an audio file's bytes; mono is doubled."""
    import numpy as np
    import soundfile as sf

    x, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return np.ascontiguousarray(x[:, :2]), int(sr)


def hot_cues_for(rb_track: RbTrack, grid) -> dict:
    return {letter: mm.cue_text(ms, grid) for letter, ms in rb_track.cues.items()}


class Session:
    """What a run shares: the project, the repo, the open rekordbox reader and the separator."""

    def __init__(self, args, stack: contextlib.ExitStack) -> None:
        self.args = args
        self.project = ssf.Project(Path(args.project))
        self.repo_root = Path(args.repo)
        self.repo = check_repo.load_repo(self.repo_root)
        self.root = Path(args.root) if getattr(args, "root", None) else None
        self.reader = None
        if args.rekordbox:
            self.reader = stack.enter_context(open_rekordbox(Path(args.rekordbox)))
        self._separator = None
        self._by_base: dict[str, list[ssf.TrackRef]] | None = None

    def separate(self, x, sr):
        if self._separator is None:
            self._separator = make_separator(self.args.device)
        return self._separator(x, sr)

    def script_anchors(self, ref: ssf.TrackRef) -> list[tuple[int, float]]:
        path = self.project.script_path(ref.guid)
        if not path.is_file():
            raise Refused(f"no script file {path.name}")
        tempo = ssf.parse_script(path.read_bytes()).tempo
        if not tempo:
            raise Refused("the script has no tempo")
        return [(int(ms), float(bpm)) for ms, bpm in tempo]

    def ref_for(self, rb_track: RbTrack) -> ssf.TrackRef:
        if self._by_base is None:
            self._by_base = {}
            for ref in self.project.trackmap():
                self._by_base.setdefault(mm.fold_name(_base(ref.path)), []).append(ref)
        hits = self._by_base.get(mm.fold_name(_base(rb_track.path)), [])
        if not hits:
            raise Refused("not in the SoundSwitch project")
        if len(hits) > 1:
            raise Refused("several SoundSwitch tracks share this file name: "
                          + "; ".join(f"{r.guid} {_label(r.artist, r.title)}" for r in hits))
        return hits[0]

    def targets(self, args) -> list[tuple[str, ssf.TrackRef | None, RbTrack | None]]:
        """`(label, ref, rekordbox track)` per requested track; ref is None when the
        playlist track is unknown to SoundSwitch (the caller reports it)."""
        if args.playlist:
            if self.reader is None:
                raise SystemExit(f"--playlist needs rekordbox: set --rekordbox or {REKORDBOX_ENV}")
            out = []
            for t in self.reader.playlist(args.playlist):
                try:
                    out.append((_label(t.artist, t.title), self.ref_for(t), t))
                except Refused:
                    out.append((_label(t.artist, t.title), None, t))
            return out
        ref = self.project.resolve(args.track)
        return [(_label(ref.artist, ref.title), ref, None)]

    def cues_of(self, ref: ssf.TrackRef, known: RbTrack | None) -> tuple[RbTrack | None, str | None]:
        """`(rekordbox track, note)`: the note says why there is no track."""
        if self.reader is None:
            return None, "rekordbox not configured"
        t = known or self.reader.track_for_file(_base(ref.path))
        return (t, None) if t is not None else (None, "not in the rekordbox collection")


# ------------------------------------------------------------------ analyze ----


def analyze_one(sess: Session, ref: ssf.TrackRef, known: RbTrack | None, out: list[str]) -> None:
    track = pool_track(sess.repo, ref)
    path = map_path(sess.repo_root, track)
    anchors = sess.script_anchors(ref)
    if sess.root is None:
        raise SystemExit(f"set --root or {ROOT_ENV}")
    audio = mm.find_audio(sess.root, ref.path)
    verdict = "written"
    raw = audio.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()[:12]
    if path.is_file() and not sess.args.force:
        existing = mm.load_map(path)
        if not mm.problems_map(existing) and not mm.is_stale(existing, audio_sha=sha, guid=ref.guid.upper(),
                                                              anchors=anchors):
            out.append(f"kept {path}")
            return
        verdict = "redone (stale)"
    x, sr = read_audio(raw)
    stems, stem_sr = sess.separate(x, sr)
    if sess.args.keep_stems:
        import soundfile as sf

        folder = Path(sess.args.keep_stems) / mm.slug(track)
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in stems.items():
            sf.write(folder / f"{name}.flac", data, stem_sr, format="FLAC")
    rb_track, note = sess.cues_of(ref, known)
    grid = ssf.Grid(anchors)
    data = mm.build_map(
        track=track, guid=ref.guid.upper(), audio_sha=sha, audio_ms=round(len(x) / sr * 1000),
        anchors=anchors, stems=stems, sr=stem_sr,
        hot_cues=None if rb_track is None else hot_cues_for(rb_track, grid),
        hot_cues_note=note, separator=SEPARATOR_NAME)
    problems = mm.problems_map(data)
    if problems:
        raise Refused("the map would break the schema: " + "; ".join(problems))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mm.dump_map(data), encoding="utf-8")
    out.append(f"{verdict} {path}")
    if "grid_warning" in data:
        out.append(f"grid warning: {track}: {data['grid_warning']}")


def run_targets(sess: Session, args, handler) -> int:
    refused = 0
    for label, ref, known in sess.targets(args):
        lines: list[str] = []
        try:
            if ref is None:
                raise Refused("not in the SoundSwitch project")
            handler(sess, ref, known, lines)
        except (Refused, LookupError, OSError, ValueError, RuntimeError, yaml.YAMLError) as e:
            lines.append(f"refused {label}: {e}")
            refused += 1
        print("\n".join(lines), flush=True)
    return 1 if refused else 0


def cmd_analyze(args) -> int:
    with contextlib.ExitStack() as stack:
        sess = Session(args, stack)
        return run_targets(sess, args, analyze_one)


# --------------------------------------------------------------------- cues ----


def cues_one(sess: Session, ref: ssf.TrackRef, known: RbTrack | None, out: list[str]) -> None:
    path = map_path(sess.repo_root, pool_track(sess.repo, ref))
    if not path.is_file():
        raise Refused(f"no map at {path}: run analyze first")
    data = mm.load_map(path)
    grid = ssf.Grid([(int(ms), float(bpm)) for ms, bpm in data["grid"]["anchors"]])
    rb_track, note = sess.cues_of(ref, known)
    new = {"hot_cues": None if rb_track is None else hot_cues_for(rb_track, grid)}
    if rb_track is None:
        new["hot_cues_note"] = note
    block = mm.dump_map(new).splitlines()[1:]  # without the generated-by comment
    lines = path.read_text(encoding="utf-8").splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith("hot_cues:")), None)
    if at is None:
        raise Refused(f"{path} has no hot_cues line: run analyze --force")
    kept = [line for line in lines if not line.startswith(("hot_cues:", "hot_cues_note:"))]
    kept[at:at] = block
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    out.append(f"cues {path}")


def cmd_cues(args) -> int:
    if not args.rekordbox:
        print(f"set --rekordbox or {REKORDBOX_ENV}", file=sys.stderr)
        return 2
    with contextlib.ExitStack() as stack:
        sess = Session(args, stack)
        return run_targets(sess, args, cues_one)


# --------------------------------------------------------------------- show ----


def find_map(repo_root: Path, text: str) -> Path:
    p = Path(text)
    if p.is_file():
        return p
    folder = repo_root / "lightshows" / "maps"
    for cand in (folder / f"{text}.yml", folder / f"{mm.slug(text)}.yml"):
        if cand.is_file():
            return cand
    words = check_repo.norm(text).split()
    hits = []
    for cand in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
        try:
            data = mm.load_map(cand)
        except (yaml.YAMLError, OSError):
            continue  # the validator reports a map that does not parse
        track = data.get("track") if isinstance(data, dict) else None
        if words and isinstance(track, str) and all(w in check_repo.norm(track) for w in words):
            hits.append(cand)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"no map matches {text!r} in {folder}")
    raise LookupError(f"{len(hits)} maps match {text!r}: " + ", ".join(h.name for h in hits))


def _cue_bar(where: str) -> int:
    return int(where.split(".")[0])


def render_map(data: dict) -> list[str]:
    bars = data["bars"]
    out = [f"{data['track']}  ·  {data['grid']['bpm']} BPM  ·  {bars} bars  ·  {data['separator']}"]
    if "grid_warning" in data:
        out.append(f"grid warning: {data['grid_warning']}")
    if data.get("hot_cues_note"):
        out.append(f"hot cues: {data['hot_cues_note']}")
    cues = data.get("hot_cues") or {}
    section = ["."] * bars
    for s in data["sections"]:
        for b in range(s["bars"][0], s["bars"][1] + 1):
            section[b - 1] = SECTION_LETTERS[s["kind"]]
    for start in range(1, bars + 1, SHOW_BARS):
        end = min(start + SHOW_BARS - 1, bars)
        out.append(f"bars {start}-{end}")
        ruler = [" "] * (end - start + 1)
        for b in range(start, end + 1, 8):
            for i, ch in enumerate(str(b)):
                if b - start + i < len(ruler):
                    ruler[b - start + i] = ch
        out.append((" " * LABEL_WIDTH + "".join(ruler)).rstrip())
        marks = ["."] * (end - start + 1)
        for letter in sorted(cues):
            b = _cue_bar(cues[letter])
            if start <= b <= end:
                marks[b - start] = letter if marks[b - start] == "." else "*"
        out.append("cues".ljust(LABEL_WIDTH) + "".join(marks))
        for voice in mm.VOICES:
            out.append(voice.ljust(LABEL_WIDTH) + data["voices"][voice]["bars"][start - 1:end])
        out.append("sections".ljust(LABEL_WIDTH) + "".join(section[start - 1:end]))
    out += ["", "drops"] if data["drops"] else ["", "drops: none"]
    out += [f"  bar {d['bar']}  {d['db']} dB" for d in data["drops"]]
    out.append("phrases")
    out += [f"  {p['from']} - {p['to']}  {p['register']}  level {p['level']}" for p in data["phrases"]]
    return out


def cmd_show(args) -> int:
    print("\n".join(render_map(mm.load_map(find_map(Path(args.repo), args.track)))))
    return 0


# ----------------------------------------------------------------- timeline ----


def cmd_timeline(args) -> int:
    if not args.rekordbox:
        print(f"set --rekordbox or {REKORDBOX_ENV}", file=sys.stderr)
        return 2
    repo = check_repo.load_repo(Path(args.repo))
    tempos = stl.block_tempos(Path(args.block).read_text(encoding="utf-8")) if args.block else []
    with contextlib.ExitStack() as stack:
        tracks = stack.enter_context(open_rekordbox(Path(args.rekordbox))).playlist(args.playlist)
    transitions, total, warnings = [], 0.0, []
    chain: list[stl.Leg] = []

    def flush() -> None:
        nonlocal total
        if chain:
            t, s, w = stl.timeline(chain)
            transitions.extend(t)
            total += s
            warnings.extend(w)
            chain.clear()

    for t in tracks:
        label = _label(t.artist, t.title)
        try:
            name = pool_track(repo, ssf.TrackRef(guid="", title=t.title, artist=t.artist, path=t.path, bpm=None, duration_ms=None))
            path = map_path(Path(args.repo), name)
            if not path.is_file():
                raise Refused(f"no map at {path}: run analyze first")
            data = mm.load_map(path)
        except (Refused, OSError, yaml.YAMLError) as e:
            warnings.append(f"no map for {label}: {e}; the chain breaks here")
            flush()
            continue
        tempo = next((tp for a, ti, tp in tempos if check_repo.same_track(t.artist, t.title, a, ti)), None)
        chain.append(stl.Leg(name, data, dict(t.cues), tempo))
    flush()
    render = stl.render_yaml if args.yaml else stl.render_markdown
    print(render(transitions, total, warnings))
    return 0


# --------------------------------------------------------------------- main ----


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, audio: bool):
        p.add_argument("track", nargs="?", help="GUID, GUID prefix or 'Artist — Title'")
        p.add_argument("--playlist", help="a rekordbox playlist, instead of a track")
        p.add_argument("--project", default=os.environ.get(PROJECT_ENV),
                       help=f"SoundSwitch project folder (default: ${PROJECT_ENV})")
        p.add_argument("--rekordbox", default=os.environ.get(REKORDBOX_ENV),
                       help=f"folder with rekordbox's master.db (default: ${REKORDBOX_ENV})")
        p.add_argument("--repo", default=str(DEFAULT_REPO), help="the NEXTRACK repo (default: this one)")
        if audio:
            p.add_argument("--root", default=os.environ.get(ROOT_ENV),
                           help=f"audio library root (default: ${ROOT_ENV})")

    a = sub.add_parser("analyze", help="make the map of a track or of a rekordbox playlist")
    common(a, True)
    a.add_argument("--force", action="store_true", help="redo maps that are up to date")
    a.add_argument("--keep-stems", metavar="DIR", help="also write the four stems under DIR/<slug>/")
    a.add_argument("--device", choices=("cuda", "cpu"), help="default: cuda when there is one")
    c = sub.add_parser("cues", help="reread the hot cues from rekordbox into existing maps")
    common(c, False)
    s = sub.add_parser("show", help="print a map as text")
    s.add_argument("track", help="a map file, its slug or the track's words")
    s.add_argument("--repo", default=str(DEFAULT_REPO), help="the NEXTRACK repo (default: this one)")

    t = sub.add_parser("timeline", help="print the set timeline of a rekordbox playlist")
    t.add_argument("--playlist", required=True, help="a rekordbox playlist")
    t.add_argument("--block", metavar="FILE", help="a block whose tracklist gives the played tempos")
    t.add_argument("--yaml", action="store_true", help="YAML instead of a Markdown table")
    t.add_argument("--rekordbox", default=os.environ.get(REKORDBOX_ENV),
                   help=f"folder with rekordbox's master.db (default: ${REKORDBOX_ENV})")
    t.add_argument("--repo", default=str(DEFAULT_REPO), help="the NEXTRACK repo (default: this one)")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "show":
            return cmd_show(args)
        if args.cmd == "timeline":
            return cmd_timeline(args)
        if bool(args.track) == bool(args.playlist):
            print("give a track or --playlist, not both", file=sys.stderr)
            return 2
        if not args.project:
            print(f"set --project or {PROJECT_ENV}", file=sys.stderr)
            return 2
        if not Path(args.project).is_dir():
            print(f"project folder not found: {args.project}", file=sys.stderr)
            return 2
        if args.cmd == "analyze" and not args.root:
            print(f"set --root or {ROOT_ENV}", file=sys.stderr)
            return 2
        return {"analyze": cmd_analyze, "cues": cmd_cues}[args.cmd](args)
    except (LookupError, OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
