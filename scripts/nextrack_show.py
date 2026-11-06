#!/usr/bin/env python3
"""nextrack_show.py — build, report on and describe a show (lightshows/shows/<id>/).

A show is a folder: `show.yml` (palette, looks, rules) and one file per track, written in
the show language. The compiler turns it into the choreographies in `lightshows/tracks/`.

Subcommands:
  build   compile the show, run its rules, write the choreographies (--check: write nothing,
          --out DIR: write elsewhere, --adopt: take over hand-written files); name the stale
          files the show owns but no longer compiles, never deleting them; print the advice
  report  the night as text, one line per section, for a critic
  vocab   the anchors, the layer words and keys, the gestures and the rules; with a show, its
          palette and looks

SHOW is a folder path or the id of a folder under <repo>/lightshows/shows/; a relative path is
looked up under --repo first (<repo>/SHOW, then <repo>/lightshows/shows/SHOW), then from the
current folder. Findings print as `path:line: rule-id: message`. Exit status: 0 clean,
1 findings (or stale files), 2 usage. Only `build` writes, and only the choreographies. See
scripts/README.md.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import check_repo
import lightshow
import show_gestures
import show_language
import show_room
import show_rules
import show_views
from show_language import CompiledShow, ShowFinding, ShowSource

DEFAULT_REPO = Path(__file__).resolve().parent.parent
TRACKS_DIR = "lightshows/tracks"
RATES = ("1/16", "1/8", "1/4", "1/2", "<n>bar")
ANCHOR_GRAMMAR = """anchor := term [ ("+" | "-") n ]
term   := n                  an absolute bar (from 1)
        | A … H              the bar of that hot cue in the map (`hot_cues`)
        | <kind>.<i>         the first bar of the i-th section of that kind (from 1)
        | <kind>.<i>.end     its last bar
        | end                the map's last bar
kind   := intro | groove | break | build | drop | outro"""


# ----------------------------------------------------------------- helpers --


def _finding_line(f) -> str:
    return f"{f.path}:{f.line}: {f.rule}: {f.message}"


def _print_findings(findings) -> None:
    for f in findings:
        print(_finding_line(f))
    if findings:
        print(f"{len(findings)} finding(s)")


def _print_advice(advice) -> None:
    """The show's design goals that do not hold yet, `show-advice` lines and `N advice`."""
    for f in advice:
        print(_finding_line(f))
    if advice:
        print(f"{len(advice)} advice")


def _title(track: str) -> str:
    return track.split(" — ", 1)[-1]


def _first_paragraph(text: str) -> str:
    return " ".join(text.split("\n\n", 1)[0].split())


def show_candidates(arg: str, root: Path) -> list[Path]:
    """Where `arg` may name a show folder, in order: an absolute path as given; a relative one
    under the repo first (`<repo>/<arg>`, then `<repo>/lightshows/shows/<arg>` for an id), then
    from the current folder."""
    path = Path(arg)
    if path.is_absolute():
        return [path]
    return [root / arg, root / check_repo.SHOWS_DIR / arg, path.absolute()]


def resolve_show(arg: str, root: Path) -> Path | None:
    """The show folder `arg` names (the first of `show_candidates` with a `show.yml`), or None."""
    for candidate in show_candidates(arg, root):
        if (candidate / "show.yml").is_file():
            return candidate.resolve()
    return None


def _load(args) -> tuple[check_repo.Repo, ShowSource | None, list]:
    """The repo, the show (None when it is unknown or does not parse) and the loader's errors."""
    root = Path(args.repo).resolve()
    folder = resolve_show(args.show, root)
    if folder is None:
        tried = ", ".join(str(c) for c in show_candidates(args.show, root))
        print(f"usage error: {args.show!r} is not a show folder or the id of one under "
              f"{check_repo.SHOWS_DIR}/: none of {tried} has a show.yml", file=sys.stderr)
        return None, None, []  # type: ignore[return-value]
    errors: list = []
    source = check_repo.load_show_folder(root, folder, errors)
    repo = check_repo.load_repo(root)
    return repo, source, errors


# ------------------------------------------------------------------- build --


def _existing(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (UnicodeDecodeError, OSError):
        return ""  # unreadable: not ours, and different from anything we would write


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".tmp")
    try:
        staged.write_text(text, encoding="utf-8")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _build(args) -> int:
    repo, source, errors = _load(args)
    if repo is None:
        return 2
    if errors or source is None or source.parse_failed:
        _print_findings(errors)
        return 1
    if not args.out and not source.folder.startswith(check_repo.SHOWS_DIR + "/"):
        print(f"usage error: the show {repo.root / source.folder} is not under "
              f"{repo.root / check_repo.SHOWS_DIR}/; a show outside lightshows/shows/ builds only with --out DIR",
              file=sys.stderr)
        return 2
    compiled, found, rule_found, advice = show_rules.evaluate_show(source, check_repo.show_inputs(repo, source))
    if found or compiled is None:
        _print_findings(found)
        return 1
    out_dir = Path(args.out) if args.out else None
    plan = []  # (shown path, target, text, state)
    refused = []
    for track in compiled.tracks:
        target = (out_dir or repo.root / TRACKS_DIR) / f"{track.slug}.yml"
        shown = str(target) if out_dir else target.relative_to(repo.root).as_posix()
        text = show_language.emit_choreography(track.choreography, source.folder)
        current = _existing(target)
        owner = show_language.owner_of(current) if current else None
        if current is not None and current != text and not out_dir and not args.check:
            if owner is None and not args.adopt:
                refused.append(f"refused {shown}: not generated by a show; use --adopt to take it over")
            elif owner is not None and owner != source.folder:
                refused.append(f"refused {shown}: generated by {owner}, not by {source.folder}")
        plan.append((shown, target, text, "unchanged" if current == text else "changed"))
    if refused:
        print("\n".join(refused))
        return 1
    for shown, target, text, state in plan:
        if args.check:
            if state == "changed":
                print(f"would change {shown}")
        elif state == "changed":
            _write_atomic(target, text)
            print(f"wrote {shown}")
        else:
            print(f"unchanged {shown}")
    stale = _stale(out_dir or repo.root / TRACKS_DIR, source.folder, {t.slug for t in compiled.tracks})
    for path in stale:
        shown = str(path) if out_dir else path.relative_to(repo.root).as_posix()
        print(f"stale {shown}: owned by this show, which no longer compiles it; delete it")
    _print_findings(rule_found)
    _print_advice(advice)              # goals: printed, never part of the exit status
    drift = args.check and any(state == "changed" for *_, state in plan)
    return 1 if drift or stale or rule_found else 0


def _stale(folder: Path, owner: str, slugs: set[str]) -> list[Path]:
    """The choreographies in `folder` whose header names `owner` and whose track it no longer
    compiles. `build` names them and never deletes them."""
    out = []
    for path in sorted(folder.glob("*.yml")):
        text = _existing(path)
        if path.stem not in slugs and text and show_language.owner_of(text) == owner:
            out.append(path)
    return out


# ------------------------------------------------------------------ report --


def _bar_of(beat: object) -> int | None:
    try:
        return int(str(beat).split(".")[0])
    except ValueError:
        return None


def _colour_name(value: object, names: dict[str, str]):
    if isinstance(value, list):
        return ",".join(str(_colour_name(v, names)) for v in value)
    return names.get(str(value).upper(), value) if isinstance(value, str) else value


_HEAD_KEYS = ("move", "draw", "state")  # the one bare word that opens a layer


def _value_text(item: object) -> str:
    if isinstance(item, list):
        return "[" + ", ".join(str(i) for i in item) + "]"
    text = str(item)
    return f'"{text}"' if " " in text else text


def _layer_text(name: str, value: object, names: dict[str, str]) -> str:
    """`name HEAD key=value ...`: the move, draw or state as a bare word, every other field as
    `key=value` (lists in brackets, text with spaces in quotes, true flags as the bare key)."""
    value = show_language.layer_word(value)
    if not isinstance(value, dict):
        return f"{name} {value}"
    head = [str(value[k]) for k in _HEAD_KEYS if value.get(k) is not None]
    parts = []
    for key, item in value.items():
        if item is None or item is False or key in _HEAD_KEYS:
            continue
        if key == "colour":
            item = _colour_name(item, names)
        parts.append(key if item is True else f"{key}={_value_text(item)}")
    return " ".join([name, *head, *parts])


def _source_text(origin) -> str:
    if origin.kind in ("bridge", "handover"):
        return origin.kind + (f" {origin.look}" if origin.look else "")
    if origin.gesture:
        return f"gesture {origin.gesture}"
    return f"look {origin.look}" if origin.look else "look (inline)"


def _music(section, data: dict) -> str:
    a, b = section.bars
    parts = []
    for sec in data.get("sections", []):
        sa, sb = sec["bars"]
        if sa <= b and sb >= a:
            parts.append(f"{sec['kind']} {max(a, sa)}-{min(b, sb)}")
    for drop in data.get("drops", []):
        if drop["bar"] == a:
            parts.append(f"drop {drop['db']:+.1f} dB")
    return ", ".join(parts)


def _share(seconds: float, total: float) -> str:
    return f"{round(100 * seconds / total)}%" if total > 0 else "0%"


def _timed(items: dict) -> str:
    """`name m:ss, name m:ss` of a `{name: seconds}` map, longest first (ties by name)."""
    ranked = sorted(items.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k} {show_views.clock_text(v)}" for k, v in ranked if v > 0) or "-"


def _night_lines(summary: dict) -> list[str]:
    """The night summary, one line per category (spec section 3)."""
    total = summary["total_s"]
    clock = show_views.clock_text
    looks = dict(summary["looks"])
    if summary["autoscript_s"] > 0:
        looks["autoscript"] = summary["autoscript_s"]
    pending = ", ".join(f"{a} -> {fb or 'no fallback'}" for a, fb in summary["pending_aims"])
    dark = summary["total_dark"]
    events = ", ".join(f"{k} {v['count']} ({clock(v['s'])})" for k, v in summary["events"].items())
    zones = ", ".join(f"{g} {clock(summary['zones'][g])} ({_share(summary['zones'][g], total)})"
                      for g in show_views.COLOUR_GROUPS)
    out = [f"night {clock(total)}", f"  looks: {_timed(looks)}"]
    out += [f"  colours {group}: {_timed(summary['colours'][group])}" for group in show_views.COLOUR_GROUPS]
    out += [f"  aims: {_timed(summary['aims'])}" + (f" · pending, played by fallback: {pending}" if pending else ""),
            f"  zones lit: {zones}",
            f"  centre dark: {clock(summary['centre_dark_s'])} ({_share(summary['centre_dark_s'], total)})",
            f"  total dark: {clock(dark['s'])} in {dark['count']} section(s)",
            f"  events: {events}",
            "  light level: an index from 0 to 9, not a measurement, rounded half up; "
            "formula in lightshows/shows/README.md"]
    return out


def _strip_block(music: str, light: str, first: int, width: int = 64) -> list[str]:
    """The two strips wrapped at `width` bars, music chunk then light chunk, each row labelled
    with the track bar of its first character: `  music   57 |...|`."""
    out = []
    for i in range(0, max(len(music), len(light), 1), width):
        for label, text in (("music", music), ("light", light)):
            out.append(f"  {label} {first + i:>4} |{text[i:i + width]}|")
    return out


_LEGEND = ("  legend: strips show one digit per bar, music level 0-9 (the highest of kick, bass, other) and "
           "light level 0-9 (an index); ~ is unknown (the autoscript decides). voices: k kick, b bass, "
           "v vocals, p perc, o other. ~ in peaks and hit checks is unknown too.")


def _layers_named(sec, room) -> dict:
    """The section's layers with the movers' presets named by aim id (`show_views.section_aims`)."""
    layers = dict(sec.layers)
    movers = show_language.layer_word(layers.get("movers"))
    if isinstance(movers, dict) and ("positions" in movers or "position" in movers):
        named = show_views.section_aims(sec, room)
        movers = dict(movers)
        if isinstance(movers.get("positions"), list):
            movers["positions"] = named
        elif named:
            movers["position"] = named[0]
        layers["movers"] = movers
    return layers


_VOICE_LETTER = {"kick": "k", "bass": "b", "vocals": "v", "perc": "p", "other": "o"}


def _voices_text(levels: dict) -> str:
    return " ".join(f"{_VOICE_LETTER[name]}{level}" for name, level in levels.items())


def _level_pair(row: dict) -> str:
    def one(level):
        return "~" if level is None else str(level)

    return f"light {one(row['before'])}>{one(row['at'])}"


def _peak_lines(rows: list[dict]) -> list[str]:
    out = ["", "peaks",
           "  clock · track bar · drop vs the two bars before · music level · light level before>at · accents · moment"]
    for r in rows:
        db = "-" if r["db"] is None else f"{r['db']:+.1f} dB"
        out.append(f"  {show_views.clock_text(r['clock_s'])} · {_title(r['track'])} {r['bar']} · {db} · "
                   f"music {r['music']} · {_level_pair(r)} · accents {','.join(r['accents']) or '-'} · "
                   f"moment {r['moment'] or '-'}")
    return out


def _hit_lines(rows: list[dict]) -> list[str]:
    out = ["", "hit checks",
           "  clock · track bar · arrival or moment · kick onset on the first step · light level before>at · "
           "accents · voices of the total dark before"]
    for r in rows:
        kind = " ".join(x for x in ("arrival" if r["arrival"] else "",
                                    f"moment {r['moment']}" if r["moment"] else "") if x)
        line = (f"  {show_views.clock_text(r['clock_s'])} · {_title(r['track'])} {r['bar']} · {kind} · "
                f"kick {r['kick']} · {_level_pair(r)} · accents {','.join(r['accents']) or '-'}")
        dark = r["dark"]
        if dark:
            other = f"{_title(dark['track'])} " if dark["track"] != r["track"] else ""
            line += f" · dark before: {other}{dark['bars'][0]}-{dark['bars'][1]} {_voices_text(dark['voices'])}"
        out.append(line)
    return out


def render_report(show: CompiledShow, findings: list[ShowFinding], advice: list[ShowFinding],
                  clock: show_views.ShowClock, room: show_room.Room | None) -> str:
    """The night as text: the night summary, each track (header with its clock and arrival, the
    two strips, a line per section starting with the clock and with the voices after
    `music:`), the peak table, the hit checks, the budget, the arrivals, the advice (the
    `show-advice` findings, goals that do not hold yet), the compiler's decisions and the
    findings. Facts only; every number comes from `show_views`."""
    palette = show.data.get("palette") or {}
    names = {str(hexa).upper(): name for name, hexa in palette.items()}
    out: list[str] = [*_night_lines(show_views.night_summary(show, clock, room)), _LEGEND]
    for n, (track, tc) in enumerate(zip(show.tracks, clock.tracks), 1):
        cues = track.map.get("hot_cues") or {}
        marks = [f"{key} {_bar_of(cues[key])}" for key in ("B", "G") if key in cues]
        head = [f"{n}. {track.track}", f"{track.map.get('bars')} bars", *marks,
                f"enters {show_views.clock_text(tc.start_s)}"]
        arrival = next((s for s in track.sections if s.origin.role == "arrival"), None)
        if arrival is not None:
            head.append(f"arrival {arrival.bars[0]} at {show_views.clock_text(tc.at(arrival.bars[0]))}")
        music_strip, light_strip = show_views.strips(track, tc)
        out += ["", " · ".join(head), *_strip_block(music_strip, light_strip, tc.leg[0])]
        for sec in track.sections:
            a, b = sec.bars
            named = _layers_named(sec, room)
            layers = "; ".join(_layer_text(k, named[k], names) for k in lightshow.LAYERS if k in named)
            tags = [t for t in (sec.origin.role, f"moment {sec.origin.moment}" if sec.origin.moment else None) if t]
            music = ", ".join(x for x in (_music(sec, track.map),
                                          _voices_text(show_views.voices(track.map, a, b))) if x)
            cells = [f"  {show_views.clock_text(tc.at(a))} {a}-{b} {sec.name}", _source_text(sec.origin), layers,
                     *tags, f"music: {music}"]
            out.append(" | ".join(cells))
    out += _peak_lines(show_views.peaks(show, clock))
    out += _hit_lines(show_views.hit_checks(show, clock))
    budget = (show.data.get("rules") or {}).get("budget") or {}
    if budget:
        out += ["", "budget"]
        for key, limits in budget.items():
            found = show_rules.occurrences(show, key)
            top = (limits or {}).get("max")
            listed = ", ".join(f"{_title(o.track)} {o.bar}" for o in found)
            out.append(f"  {key}: max {'-' if top is None else top}, used {len(found)}"
                       + (f": {listed}" if listed else ""))
    arrivals = []
    for track in show.tracks:
        for sec in track.sections:
            if sec.origin.role == "arrival":
                matrix = show_language.layer_word(sec.layers.get("matrix"))
                draw = matrix.get("draw") if isinstance(matrix, dict) else matrix
                colour = _colour_name(matrix.get("colour"), names) if isinstance(matrix, dict) else None
                arrivals.append(f"  {_title(track.track)} {sec.bars[0]}: draw {draw}, colour {colour}")
    if arrivals:
        out += ["", "arrivals", *arrivals]
    if advice:
        out += ["", "advice", *(f"  {_finding_line(f)}" for f in advice)]
    if show.decisions:
        out += ["", "decided by the compiler", *(f"  {d}" for d in show.decisions)]
    if findings:
        out += ["", *(_finding_line(f) for f in findings), f"{len(findings)} finding(s)"]
    return "\n".join(out) + "\n"


def _report(args) -> int:
    repo, source, errors = _load(args)
    if repo is None:
        return 2
    if errors or source is None or source.parse_failed:
        _print_findings(errors)
        return 1
    compiled, found, rule_found, advice = show_rules.evaluate_show(source, check_repo.show_inputs(repo, source))
    if found or compiled is None:
        _print_findings(found)
        return 1
    clock = show_views.build_clock(compiled, check_repo.show_tempos(repo, source))
    print(render_report(compiled, rule_found, advice, clock, check_repo.valid_room(repo)), end="")
    return 1 if rule_found else 0


# ------------------------------------------------------------------- vocab --


def _layer_forms(layer: str) -> str:
    """`auto | off | ... | {key, ...}`: the words a layer takes, then its mapping keys."""
    forms = list(lightshow.SCALARS[layer])
    if layer in show_language.LAYER_KEYS:
        forms.append("{" + ", ".join(show_language.LAYER_KEYS[layer]) + "}")
    return " | ".join(forms)


def _point(p) -> str:
    return "[" + ", ".join(repr(float(v)) for v in p) + "]"


def _aims_text(room: show_room.Room) -> list[str]:
    """The room's aims: the configured ones (id -> preset, figure), then the pending ones, the
    presets still to create in SoundSwitch, with their fallback and each mover's target."""
    configured = [a for a in room.aims.values() if a.status == "configured"]
    pending = [a for a in room.aims.values() if a.status == "pending"]
    out = ["", "aims (room.yml): an aim id stands wherever a preset name stands"]
    out += [f"  {a.id} -> {a.preset} · {a.figure}" for a in configured]
    if pending:
        out += ["", "presets to create in SoundSwitch" + (" (geometria presumida)" if room.assumed else "")]
        for a in pending:
            out.append(f"  {a.id} -> {a.preset} · {a.figure}")
            out.append(f"    fallback: {a.fallback}")
            out.append("    targets: " + "; ".join(f"{k} at {_point(p)}" for k, p in a.targets.items()))
    return out


def render_vocab(source: ShowSource | None, room: show_room.Room | None = None) -> str:
    """What an agent needs to write a show: anchors, layer words, gestures, rules, the room's
    aims when it has a valid one, and with a show its palette and looks."""
    out = ["anchors", *(f"  {line}" for line in ANCHOR_GRAMMAR.splitlines()),
           "  example: on a map with drops at 9 and 21 and hot cue G at 25, `drop.2 - 1` is bar 20,",
           "  `G` is 25, `end` is the last bar and `break.1.end + 1` is the bar after the first break.",
           "  A hot cue off the first beat (9.3) cannot be an anchor. `faster_from` takes an anchor too.",
           "",
           "layers",
           f"  layers: {', '.join(lightshow.LAYERS)} (haze is held by every compile)",
           "  each layer takes one of its words or a mapping of its keys:",
           *(f"  {layer}: {_layer_forms(layer)}" for layer in lightshow.LAYERS),
           f"  movers move: {', '.join(lightshow.MOVER_MOVES)}",
           f"  matrix draw: {', '.join(lightshow.MATRIX_DRAWS)}",
           f"  hue state: {', '.join(lightshow.HUE_STATES)}",
           f"  rates: {' '.join(RATES)}",
           f"  accents: {', '.join(show_language.ACCENTS)}; effect keys: {', '.join(show_rules.EFFECT_KEYS)}",
           ""]
    for name, g in show_gestures.GESTURES.items():
        out.append(f"gesture {name}: {_first_paragraph(g.doc)}")
        out += [f"    {param}: {desc}" for param, desc in g.params.items()]
        out.append(f"    example ({g.example_bars} bars): with: {g.example}")
    out.append("")
    for name, r in show_rules.RULES.items():
        out.append(f"rule {name}: {_first_paragraph(r.doc)}")
        out.append(f"    params: {r.params}")
    if room is not None:
        out += _aims_text(room)
    if source is not None and isinstance(source.show, dict):
        data = show_language.clean(source.show)
        out += ["", f"palette of {source.show_id}"]
        out += [f"  {name} = {hexa}" for name, hexa in (data.get("palette") or {}).items()]
        flat, _ = show_language.flatten_looks(data.get("looks") or {})
        out += ["", f"looks of {source.show_id}"]
        for name, layers in flat.items():
            out.append(f"  look {name}: " + "; ".join(
                _layer_text(k, layers[k], {}) for k in lightshow.LAYERS if k in layers))
    return "\n".join(out) + "\n"


def _vocab(args) -> int:
    source = None
    if args.show:
        repo, source, errors = _load(args)
        if repo is None:
            return 2
        if errors:
            _print_findings(errors)
            return 1
    else:
        repo = check_repo.load_repo(Path(args.repo).resolve())
    print(render_vocab(source, check_repo.valid_room(repo)), end="")
    return 0


# -------------------------------------------------------------------- main --


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, report on and describe a show.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_: str, show_required: bool = True):
        p = sub.add_parser(name, help=help_)
        p.add_argument("show", nargs=None if show_required else "?",
                       help="a show folder, or the id of a folder under lightshows/shows/")
        p.add_argument("--repo", type=Path, default=DEFAULT_REPO,
                       help="repo root (default: the repo that holds this script)")
        return p

    build = add("build", "compile the show and write lightshows/tracks/*.yml")
    build.add_argument("--check", action="store_true", help="write nothing; exit 1 if a file would change")
    build.add_argument("--out", type=Path, help="write the choreographies into DIR instead (a variant)")
    build.add_argument("--adopt", action="store_true", help="take over hand-written files")
    add("report", "the night as text, for a critic")
    add("vocab", "anchors, layer words, gestures and rules (and a show's palette and looks)", show_required=False)
    args = parser.parse_args(argv)
    return {"build": _build, "report": _report, "vocab": _vocab}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
