#!/usr/bin/env python3
"""nextrack_show.py — build, report on and describe a show (lightshows/shows/<id>/).

A show is a folder: `show.yml` (palette, looks, rules) and one file per track, written in
the show language. The compiler turns it into the choreographies in `lightshows/tracks/`.

Subcommands:
  build   compile the show, run its rules, write the choreographies (--check: write nothing,
          --out DIR: write elsewhere, --adopt: take over hand-written files); name the stale
          files the show owns but no longer compiles, never deleting them; print the advice
  report  the night as text, one line per section, for a critic, with the energy measures and
          the six analyses (follows, drops, builds, variety, arc, identity); --track cuts it to
          one track and its neighbours' handover and bridge, --section to named sections
  zoom    a moment at 1/16 of a beat: the map's music lanes over the light `build` would
          compile, and with --frames the Vorlanes' 8x7 cells (needs no SoundSwitch project;
          rule findings are the report's: it counts them on stderr and exits 1 only on source
          findings)
  compare the facts of two shows side by side (arrivals, moments, drops, signatures, looks,
          colours, windows, findings); --keep A,B exits 1 when a kept fact differs
  brief   a set's music for the director: clock, energy per track, drops ranked, target arc,
          label questions, what is missing (SET is a set path or the stem of sets/<stem>.md;
          it needs no show)
  book    the book of the night: one self-contained HTML page in pt-BR for the owner (concept,
          palette, signatures, vocabulary, arc, moments, rhythm, track by track, limits,
          advice), with the latest run of <show folder>/ledger.md when there is one; -o FILE
  vocab   the anchors, the layer words and keys, the gestures and the rules; with a show, its
          palette and looks

SHOW is a folder path or the id of a folder under <repo>/lightshows/shows/; a relative path is
looked up under --repo first (<repo>/SHOW, then <repo>/lightshows/shows/SHOW), then from the
current folder. Findings print as `path:line: rule-id: message`. Exit status: 0 clean,
1 findings (or stale files), 2 usage. Only `build` and `book` write: the choreographies, and
the book's FILE. See scripts/README.md.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import check_repo
import lightshow
import show_analysis
import show_book
import show_brief
import show_compare
import show_energy
import show_gestures
import show_language
import show_report
import show_room
import show_rules
import show_views
import show_zoom
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


def _load(args, arg: str | None = None) -> tuple[check_repo.Repo, ShowSource | None, list]:
    """The repo, the show (None when it is unknown or does not parse) and the loader's errors.
    `arg` names the show when it is not `args.show`."""
    root = Path(args.repo).resolve()
    arg = args.show if arg is None else arg
    folder = resolve_show(arg, root)
    if folder is None:
        tried = ", ".join(str(c) for c in show_candidates(arg, root))
        print(f"usage error: {arg!r} is not a show folder or the id of one under "
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
    if origin.kind in ("bridge", "handover", "echo"):
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
    """The share of the night: `round(100 x seconds / total)` as a whole percent, `0%` when the
    night has no length."""
    return f"{round(100 * seconds / total)}%" if total > 0 else "0%"


def _timed(items: dict) -> str:
    """`name m:ss, name m:ss` of a `{name: seconds}` map, longest first (ties by name)."""
    ranked = sorted(items.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k} {show_views.clock_text(v)}" for k, v in ranked if v > 0) or "-"


def _night_lines(summary: dict, unknown_s: float = 0.0) -> list[str]:
    """The night summary, one line per category (spec section 3), and `unknown_s`, the seconds
    of the legs whose light is unknown (`show_report.light_unknown_s`)."""
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
            f"  light unknown: {clock(unknown_s)} ({_share(unknown_s, total)}), the autoscript decides"]
    return out


def _strip_block(strips: dict[str, str], first: int, width: int = 64) -> list[str]:
    """The four strips (`show_views.STRIP_ROWS`) wrapped at `width` bars, one row each per
    chunk, each row labelled with the track bar of its first character:
    `  music      57 |...|`."""
    out = []
    for i in range(0, max(max((len(t) for t in strips.values()), default=0), 1), width):
        for label in show_views.STRIP_ROWS:
            out.append(f"  {label:<8} {first + i:>4} |{strips[label][i:i + width]}|")
    return out


_LEGEND = ("  legend: strips show one digit 0-9 per bar: music is E_music (loudness, brightness, onset "
           "density, texture; track scope), light is E_light (brightness and activity of the rig as the "
           "compiler writes it), bright and activity its two parts (night scope); ~ is unknown (the "
           "autoscript decides) and stays out of every statistic. (interim): a map without `mix`, its "
           "E_music from onset density and texture alone. voices: k kick, b bass, v vocals, p perc, o other. "
           "Formulas: lightshows/shows/README.md, The critic's views.")


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


def _peak_lines(rows: list[dict], interim: frozenset[int] = frozenset()) -> list[str]:
    """The peak table: a header, its columns and a row per drop; a track in `interim` (indices)
    is marked `(interim)`, its E_music from the interim formula."""
    out = ["", "peaks",
           "  clock · track bar · drop vs the two bars before · E_music · E_light before>at · accents · moment"]
    for r in rows:
        db = "-" if r["db"] is None else f"{r['db']:+.1f} dB"
        music = "~" if r["music"] is None else r["music"]
        name = _title(r["track"]) + (" (interim)" if r.get("index") in interim else "")
        out.append(f"  {show_views.clock_text(r['clock_s'])} · {name} {r['bar']} · {db} · "
                   f"music {music} · {_level_pair(r)} · accents {','.join(r['accents']) or '-'} · "
                   f"moment {r['moment'] or '-'}")
    return out


def _hit_lines(rows: list[dict]) -> list[str]:
    out = ["", "hit checks",
           "  clock · track bar · arrival or moment · kick onset on the first step · E_light before>at · "
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


def track_index(show: CompiledShow, name: str) -> int | None:
    """The set-order index of the show track named `name` exactly as its track file names it
    (`Artist — Title`), or None."""
    return next((i for i, t in enumerate(show.tracks) if t.track == name), None)


def _tracks_text(show: CompiledShow) -> str:
    return "; ".join(t.track for t in show.tracks)


def _section_line(sec, track, tc, room, names: dict[str, str]) -> str:
    """`clock bars name | source | layers | role and moment | music: kinds, drops, voices`."""
    a, b = sec.bars
    named = _layers_named(sec, room)
    layers = "; ".join(_layer_text(k, named[k], names) for k in lightshow.LAYERS if k in named)
    tags = [t for t in (sec.origin.role, f"moment {sec.origin.moment}" if sec.origin.moment else None) if t]
    music = ", ".join(x for x in (_music(sec, track.map), _voices_text(show_views.voices(track.map, a, b))) if x)
    cells = [f"  {show_views.clock_text(tc.at(a))} {a}-{b} {sec.name}", _source_text(sec.origin), layers,
             *tags, f"music: {music}"]
    return " | ".join(cells)


def _track_block(show: CompiledShow, clock, energy: list, room, names: dict[str, str], i: int) -> list[str]:
    """A track's header (bars, B, G, when it enters, its arrival, `(interim)`), its four
    strips and one line per compiled section."""
    track, tc = show.tracks[i], clock.tracks[i]
    cues = track.map.get("hot_cues") or {}
    marks = [f"{key} {_bar_of(cues[key])}" for key in ("B", "G") if key in cues]
    head = [f"{i + 1}. {track.track}", f"{track.map.get('bars')} bars", *marks,
            f"enters {show_views.clock_text(tc.start_s)}"]
    arrival = next((s for s in track.sections if s.origin.role == "arrival"), None)
    if arrival is not None:
        head.append(f"arrival {arrival.bars[0]} at {show_views.clock_text(tc.at(arrival.bars[0]))}")
    if energy[i].interim:
        head.append("(interim)")
    out = ["", " · ".join(head), *_strip_block(show_views.strips(track, tc, energy[i]), tc.leg[0])]
    return out + [_section_line(sec, track, tc, room, names) for sec in track.sections]


def _neighbour_lines(show: CompiledShow, clock, room, names: dict[str, str], i: int, kinds: tuple[str, ...],
                     what: str) -> list[str]:
    """Track `i`'s sections of `kinds` under `N. Artist — Title · <what>`; none without such a
    section."""
    track, tc = show.tracks[i], clock.tracks[i]
    lines = [_section_line(sec, track, tc, room, names) for sec in track.sections if sec.origin.kind in kinds]
    return ["", f"{i + 1}. {track.track} · {what}", *lines] if lines else []


def _tracks_part(show: CompiledShow, clock, energy: list, room, names: dict[str, str],
                 index: int | None) -> list[show_report.Line]:
    """The legend and every track's block; with `index`, that track's block between the
    previous track's handover (and echo) and the next track's bridge."""
    if index is None:
        out: list[show_report.Line] = [(_LEGEND, None)]
        for i in range(len(show.tracks)):
            out += [(t, frozenset({i})) for t in _track_block(show, clock, energy, room, names, i)]
        return out
    lines = [_LEGEND]
    if index > 0:
        lines += _neighbour_lines(show, clock, room, names, index - 1, ("handover", "echo"), "handover")
    lines += _track_block(show, clock, energy, room, names, index)
    if index + 1 < len(show.tracks):
        lines += _neighbour_lines(show, clock, room, names, index + 1, ("bridge",), "bridge")
    return [(t, frozenset({index})) for t in lines]


def _rows_part(lines: list[str], rows: list[dict]) -> list[show_report.Line]:
    """A table from `_peak_lines` or `_hit_lines`: its blank, header and columns are the frame,
    each row names its track."""
    return [(t, None) for t in lines[:3]] + [(t, frozenset({r["index"]})) for t, r in zip(lines[3:], rows)]


def _named_by(show: CompiledShow, path: str | None = None, text: str | None = None) -> frozenset[int]:
    """The tracks a finding's path (the track file) or a decision's text (`Title: ...`) names."""
    return frozenset(i for i, t in enumerate(show.tracks)
                     if (path is not None and t.path == path)
                     or (text is not None and text.startswith(f"{_title(t.track)}: ")))


def _track_findings(show: CompiledShow, findings: list[ShowFinding], index: int | None) -> list[ShowFinding]:
    """The findings a report prints: all, or with a track `index`, those of its track file."""
    return findings if index is None else [f for f in findings if index in _named_by(show, path=f.path)]


def _budget_part(show: CompiledShow) -> list[show_report.Line]:
    budget = (show.data.get("rules") or {}).get("budget") or {}
    if not budget:
        return []
    index = {t.track: i for i, t in enumerate(show.tracks)}
    out: list[show_report.Line] = [("", None), ("budget", None)]
    for key, limits in budget.items():
        found = show_rules.occurrences(show, key)
        top = (limits or {}).get("max")
        listed = ", ".join(f"{_title(o.track)} {o.bar}" for o in found)
        out.append((f"  {key}: max {'-' if top is None else top}, used {len(found)}"
                    + (f": {listed}" if listed else ""),
                    frozenset(index[o.track] for o in found if o.track in index)))
    return out


def _arrivals_part(show: CompiledShow, names: dict[str, str]) -> list[show_report.Line]:
    arrivals: list[show_report.Line] = []
    for i, track in enumerate(show.tracks):
        for sec in track.sections:
            if sec.origin.role == "arrival":
                matrix = show_language.layer_word(sec.layers.get("matrix"))
                draw = matrix.get("draw") if isinstance(matrix, dict) else matrix
                colour = _colour_name(matrix.get("colour"), names) if isinstance(matrix, dict) else None
                arrivals.append((f"  {_title(track.track)} {sec.bars[0]}: draw {draw}, colour {colour}",
                                 frozenset({i})))
    return [("", None), ("arrivals", None), *arrivals] if arrivals else []


def _findings_part(shown: list[ShowFinding], index: int | None) -> list[show_report.Line]:
    """The findings already cut to the report (`_track_findings`) and their count; each names
    the report's track, if any."""
    if not shown:
        return []
    names = frozenset() if index is None else frozenset({index})
    return [("", None), *((_finding_line(f), names) for f in shown), (f"{len(shown)} finding(s)", None)]


def render_report(show: CompiledShow, findings: list[ShowFinding], advice: list[ShowFinding],
                  clock: show_views.ShowClock, room: show_room.Room | None, *, track: str | None = None,
                  sections: tuple[str, ...] = show_report.REPORT_SECTIONS, set_arc: str | None = None) -> str:
    """The night as text, its sections in `show_report.REPORT_SECTIONS` order: the night
    summary; the legend and each track (header with its clock and arrival, the four strips, a
    line per section starting with the clock and with the voices after `music:`); the peak
    table and the hit checks (E_music and E_light, `show_views`); the six analyses of
    `show_analysis` (follows, drops, builds, variety, arc, identity, text from `show_report`;
    the identity's arc falls back to `set_arc`, the set's front matter); the budget, the
    arrivals, the advice (the `show-advice` findings, goals that do not hold yet), the
    compiler's decisions and the findings. Facts only. The six analyses run on the clock of
    `show_analysis.analyse` (`show_views.build_clock(show)`, the one `report` passes).

    `sections` keeps only those sections. `track` (`Artist — Title`, a track of the show; a
    ValueError otherwise) cuts the report to that track: the legend, its block between the
    previous track's handover and the next track's bridge, and in every other section the
    lines that name it (its rows, findings and advice of its file, decisions about it), a
    section with none being left out; the summary names no track and is left out."""
    index = None
    if track is not None:
        index = track_index(show, track)
        if index is None:
            raise ValueError(f"{track!r} is not a track of the show")
    palette = show.data.get("palette") or {}
    names = {str(hexa).upper(): name for name, hexa in palette.items()}
    memo: dict = {}

    def energy() -> list:
        if "energy" not in memo:
            memo["energy"] = show_energy.night_energy(show, clock)
        return memo["energy"]

    def analysis():
        if "analysis" not in memo:
            memo["analysis"] = show_analysis.analyse(show)
        return memo["analysis"]

    def summary() -> list[show_report.Line]:
        night = show_views.night_summary(show, clock, room)
        return [(t, frozenset()) for t in _night_lines(night, show_report.light_unknown_s(clock, energy()))]

    def peaks() -> list[show_report.Line]:
        rows = show_views.peaks(show, clock, energy())
        interim = frozenset(i for i, te in enumerate(energy()) if te.interim)
        return _rows_part(_peak_lines(rows, interim), rows)

    def hits() -> list[show_report.Line]:
        rows = show_views.hit_checks(show, clock, energy())
        return _rows_part(_hit_lines(rows), rows)

    def analysed(items) -> list[show_report.Line]:
        return [("", None), *items]

    def listed(header: str, lines: list[tuple[str, frozenset[int]]]) -> list[show_report.Line]:
        return [("", None), (header, None), *lines] if lines else []

    parts = {
        "summary": summary,
        "tracks": lambda: _tracks_part(show, clock, energy(), room, names, index),
        "peaks": peaks,
        "hits": hits,
        "follows": lambda: analysed(show_report.follows_items(analysis(), show)),
        "drops": lambda: analysed(show_report.drops_items(analysis(), show)),
        "builds": lambda: analysed(show_report.builds_items(analysis(), show)),
        "variety": lambda: analysed(show_report.variety_items(analysis(), show)),
        "arc": lambda: analysed(show_report.arc_items(analysis(), show)),
        "identity": lambda: analysed(show_report.identity_items(analysis(), show, set_arc)),
        "budget": lambda: _budget_part(show),
        "arrivals": lambda: _arrivals_part(show, names),
        "advice": lambda: listed("advice", [(f"  {_finding_line(f)}", _named_by(show, path=f.path)) for f in advice]),
        "decided": lambda: listed("decided by the compiler",
                                  [(f"  {d}", _named_by(show, text=d)) for d in show.decisions]),
        "findings": lambda: _findings_part(_track_findings(show, findings, index), index),
    }
    out: list[str] = []
    for name in show_report.REPORT_SECTIONS:
        if name in sections:
            out += show_report.select(parts[name](), index)
    while out and out[0] == "":
        out.pop(0)
    return "\n".join(out) + "\n" if out else ""


def _set_arc(root: Path, show: CompiledShow) -> str | None:
    """The `arc` in the front matter of the show's set (`set:` in show.yml), or None when the
    set has none or cannot be read."""
    rel = show.data.get("set") if isinstance(show.data, dict) else None
    if not isinstance(rel, str):
        return None
    try:
        text = check_repo.read_text(root / rel)
    except (OSError, UnicodeDecodeError):
        return None
    front = check_repo._split_block(rel, text, []).front
    arc = front.get("arc") if isinstance(front, dict) else None
    return arc if isinstance(arc, str) else None


def _report(args) -> int:
    sections = show_report.REPORT_SECTIONS
    if args.section is not None:
        wanted = [s.strip() for s in args.section.split(",") if s.strip()]
        bad = [s for s in wanted if s not in show_report.REPORT_SECTIONS]
        if bad or not wanted:
            return _usage(f"--section takes section names, comma-separated, from "
                          f"{', '.join(show_report.REPORT_SECTIONS)}; not {', '.join(bad) or repr(args.section)}")
        sections = tuple(s for s in show_report.REPORT_SECTIONS if s in wanted)
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
    index = None
    if args.track is not None:
        index = track_index(compiled, args.track)
        if index is None:
            return _usage(f"{args.track!r} is not a track of the show (tracks: {_tracks_text(compiled)})")
    clock = show_views.build_clock(compiled)
    print(render_report(compiled, rule_found, advice, clock, check_repo.valid_room(repo), track=args.track,
                        sections=sections, set_arc=_set_arc(repo.root, compiled)), end="")
    printed = "findings" in sections and _track_findings(compiled, rule_found, index)
    return 1 if printed else 0


# -------------------------------------------------------------------- zoom --


def _usage(message: str) -> int:
    print(f"usage error: {message}", file=sys.stderr)
    return 2


def zoom_target(show: CompiledShow, target: str, anchor: str | None) -> tuple[int, int, str | None] | str:
    """`(track index, bar, label)` of a zoom's target, or the usage error. Without `anchor`,
    `target` is a moment (`show_zoom.moment_target`); with one, it is a track as its track
    file names it (`Artist — Title`) and `anchor` a bar of its map (`resolve_anchor`). The
    label is the moment or the anchor, None for a bare bar number (the header says `bar N`)."""
    moments = ", ".join(show_zoom.moment_names(show)) or "none"
    if anchor is None:
        found = show_zoom.moment_target(show, target)
        if found is not None:
            return (*found, target)
        if any(t.track == target for t in show.tracks):
            return f'{target!r} is a track: give an anchor too (zoom SHOW "{target}" drop.1)'
        return (f"{target!r} is not a moment of the show (moments: {moments}); "
                'or give a track and an anchor (zoom SHOW "Artist — Title" ANCHOR)')
    index = track_index(show, target)
    if index is None:
        return f"{target!r} is not a track of the show (tracks: {_tracks_text(show)}; moments: {moments})"
    bar, problem = show_language.resolve_anchor(anchor, show.tracks[index].map)
    if problem is not None:
        return f"anchor of {target}: {problem}"
    return index, bar, None if anchor.strip().isdigit() else anchor


def _zoom(args) -> int:
    if args.before < 0 or args.after < 0:
        return _usage(f"--before and --after take a number of bars from 0, not {min(args.before, args.after)}")
    frames = [f.strip() for f in (args.frames or "").split(",") if f.strip()]
    bad = [f for f in frames if not show_zoom.FRAME_RE.fullmatch(f)]
    if bad:
        return _usage(f"--frames takes <bar>.<beat> beats (beat 1-4), comma-separated, not {', '.join(bad)}")
    repo, source, errors = _load(args)
    if repo is None:
        return 2
    if errors or source is None or source.parse_failed:
        _print_findings(errors)
        return 1
    compiled, found, rule_found, _ = show_rules.evaluate_show(source, check_repo.show_inputs(repo, source))
    if found or compiled is None:
        _print_findings(found)
        return 1
    target = zoom_target(compiled, args.target, args.anchor)
    if isinstance(target, str):
        return _usage(target)
    index, bar, label = target
    clock = show_views.build_clock(compiled)
    print(show_zoom.render_zoom(compiled, index, bar, args.before, args.after, frames, clock,
                                rig=check_repo.valid_rig(repo), room=check_repo.valid_room(repo), label=label), end="")
    if rule_found:                     # the report lists them; the zoom only says they exist
        print(f"{len(rule_found)} rule finding(s): see nextrack_show.py report", file=sys.stderr)
    return 0


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
    out += ["", "identity (show.yml `identity:`)",
            f"  arc: {', '.join(show_language.ARC_SHAPES)}",
            f"  signature dimensions (`is`): {', '.join(show_language.IDENTITY_DIMENSIONS)}",
            "  signature: {name, intent, is: {dimension: value or [values]}, share: {min?, max?}}"]
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


# ------------------------------------------------------------------- brief --


def _brief(args) -> int:
    root = Path(args.repo).resolve()
    rel = args.set if args.set.endswith(".md") or "/" in args.set else f"sets/{args.set}.md"
    path = (root / rel).resolve()
    if not path.is_file() or root not in path.parents:
        return _usage(f"{args.set!r} is not a set: no file {rel} under {root.name}/")
    repo = check_repo.load_repo(root)
    try:
        print(show_brief.render_brief(repo, path.relative_to(root).as_posix()), end="")
    except (OSError, UnicodeDecodeError) as e:
        return _usage(f"cannot read {rel}: {e}")
    return 0


# ----------------------------------------------------------------- compare --


def _compare_facts(args, arg: str):
    """The facts of one show of `compare`: a dict, or an exit status when it cannot be read."""
    repo, source, errors = _load(args, arg)
    if repo is None:
        return 2
    if errors or source is None or source.parse_failed:
        _print_findings(errors)
        return 1
    compiled, found, rule_found, advice = show_rules.evaluate_show(source, check_repo.show_inputs(repo, source))
    if found or compiled is None:
        _print_findings(found)
        return 1
    return show_compare.facts(compiled, rule_found, advice, check_repo.valid_room(repo))


def _compare(args) -> int:
    kept: list[str] = []
    if args.keep is not None:
        kept = [k.strip() for k in args.keep.split(",") if k.strip()]
        bad = [k for k in kept if k not in show_compare.FACTS]
        if bad or not kept:
            return _usage(f"--keep takes fact names, comma-separated, from "
                          f"{', '.join(show_compare.FACTS)}; not {', '.join(bad) or repr(args.keep)}")
    a = _compare_facts(args, args.show)
    if isinstance(a, int):
        return a
    b = _compare_facts(args, args.other)
    if isinstance(b, int):
        return b
    diff = show_compare.diff_facts(a, b)
    for fact in show_compare.FACTS:
        lines = diff[fact]
        print(f"{fact}: same" if not lines else f"{fact}:")
        for line in lines:
            print(f"  {line}")
    return 1 if any(diff[k] for k in kept) else 0


# -------------------------------------------------------------------- book --


def _book(args) -> int:
    if args.output is None:
        return _usage("book needs -o FILE, the HTML page to write")
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
    path = repo.root / source.folder / "ledger.md"
    try:
        ledger = path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError) as e:
        return _usage(f"cannot read {path}: {e}")
    try:
        _write_atomic(Path(args.output), show_book.render_book(compiled, advice, ledger,
                                                               set_arc=_set_arc(repo.root, compiled)))
    except OSError as e:
        print(f"cannot write {args.output}: {e.strerror or e}", file=sys.stderr)
        return 1
    print(f"wrote {args.output}")
    if rule_found:                     # the report lists them; the book prints the advice only
        print(f"{len(rule_found)} rule finding(s): see nextrack_show.py report", file=sys.stderr)
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
    report = add("report", "the night as text, for a critic")
    report.add_argument("--track", metavar="TEXT",
                        help='only this track ("Artist — Title"), its neighbours\' handover and bridge, and the lines '
                             "that name it")
    report.add_argument("--section", metavar="A,B",
                        help=f"only these sections: {', '.join(show_report.REPORT_SECTIONS)}")
    zoom = add("zoom", "a moment at 1/16 of a beat: the map's music over the compiled light")
    zoom.add_argument("target", help='a moment name, or a track ("Artist — Title") followed by ANCHOR')
    zoom.add_argument("anchor", nargs="?", help="with a track: its bar, as an anchor (49, G, drop.2, drop.2 - 1)")
    zoom.add_argument("--before", type=int, default=3, help="bars before the target (default 3)")
    zoom.add_argument("--after", type=int, default=1, help="bars after the target (default 1)")
    zoom.add_argument("--frames", metavar="B.b,...", help="also both Vorlanes' 8x7 cells at these beats")
    compare = add("compare", "the facts of two shows side by side; --keep exits 1 when a kept fact differs")
    compare.add_argument("other", help="the second show (a folder, or an id)")
    compare.add_argument("--keep", metavar="A,B",
                         help=f"exit 1 when one of these facts differs: {', '.join(show_compare.FACTS)}")
    book = add("book", "the book of the night: one HTML page in pt-BR for the owner")
    book.add_argument("-o", "--output", metavar="FILE", help="the HTML file to write (required)")
    add("vocab", "anchors, layer words, gestures and rules (and a show's palette and looks)", show_required=False)
    brief = sub.add_parser("brief", help="a set's music for the director: clock, energy, drops, arc (needs no show)")
    brief.add_argument("set", help="a repo-relative set path, or the stem of sets/<stem>.md")
    brief.add_argument("--repo", type=Path, default=DEFAULT_REPO,
                       help="repo root (default: the repo that holds this script)")
    args = parser.parse_args(argv)
    return {"build": _build, "report": _report, "zoom": _zoom, "compare": _compare, "book": _book, "vocab": _vocab,
            "brief": _brief}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
