"""show_brief.py — `nextrack_show.py brief <set>`: a compact, generated description of a set's
music for the agent team's director (spec section A7 of
docs/superpowers/specs/2026-11-07-show-team-design.md). It needs no show.

The text has six parts, in this order, each under its header line:
    night     the length (the set clock's total), the set's `arc`, the blocks' `function` and
              `energy`, the tempo ramp (first leg's start to last leg's end, and the extremes)
    tracks    per track, in set order: the clock (`enters` at the start of its leg, the leg's
              minutes), `B`, `G`, the mix window (the bars from `G` to the map's last bar),
              the owner's energy (`eN` of the tracklist line, else the pool's `energy`), the
              night-normalised `E_music` mean and 90th percentile over the leg's bars, the
              section strip (one letter per leg bar, the letters of `nextrack_map.py show`) and
              the vocal presence (the share of leg bars whose vocals digit is 6 or more)
    drops     the night's drops ranked by the salience of `show_analysis.map_drops` (the maps
              alone), the biggest first (a tie goes to the earlier on the clock), with bar and
              clock
    target    the owner's energy as one character per minute of the night: the tracks' owner
              energies at their legs' starts, joined by straight lines, flat before the first
              and after the last, read at the middle of each minute and rounded half up; 1-9
              are digits, 10 is `X`
    labels    the label check's questions (`show_analysis._label_questions`: owner energy rank
              against measured `E_music` rank, three places apart or more); never a fix
    missing   a track with no map (or an invalid one), a v1 map (its `E_music` uses the
              interim formula), a hot cue `B` (not the first track) or `G` (not the last)
              that the clock needs, and a track the clock leaves out

A track without a valid map has no clock: the clock runs over the tracks that have one. The
tracks of the brief keep the set's order. Same inputs give the same bytes.
"""
from __future__ import annotations

import numpy as np

import check_repo
import musical_map
import nextrack_map
import set_timeline
import show_analysis
import show_energy
import show_views

VOCAL_LEVEL = 6


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def _find_map(repo: check_repo.Repo, artist: str, title: str) -> tuple[str | None, dict | None, str | None]:
    """`(path, data, problem)` of the map of a tracklist track: the map file whose stem is the
    slug of `Artist — Title`, else the first whose `track` is `same_track`. A map that fails
    `problems_map` gives `(path, None, first problem)`; no map at all `(None, None, None)`."""
    stem = musical_map.slug(f"{artist} — {title}")
    found = next(((p, d) for p, d in repo.maps if p.rsplit("/", 1)[-1].removesuffix(".yml") == stem), None)
    if found is None:
        for p, d in repo.maps:
            name = d.get("track") if isinstance(d, dict) else None
            if isinstance(name, str) and " — " in name and check_repo.same_track(artist, title, *name.split(" — ", 1)):
                found = (p, d)
                break
    if found is None:
        return None, None, None
    problems = musical_map.problems_map(found[1])
    return found[0], (None if problems else found[1]), (problems[0] if problems else None)


def _pool_energy(repo: check_repo.Repo, artist: str, title: str) -> int | None:
    for pool in repo.pools:
        for e in pool.entries:
            if (isinstance(e.get("energy"), int) and not isinstance(e.get("energy"), bool)
                    and isinstance(e.get("artist"), str) and isinstance(e.get("title"), str)
                    and check_repo.same_track(artist, title, e["artist"], e["title"])):
                return e["energy"]
    return None


def _energy_char(value: float) -> str:
    n = int(value + 0.5 + 1e-9)
    return "X" if n >= 10 else str(max(n, 0))


def _target_strip(points: list[tuple[float, int]], total_s: float) -> str:
    """One character per minute (module docstring, `target`)."""
    if not points or total_s <= 0:
        return ""
    out = []
    for m in range(int(-(-total_s // 60))):
        t = 60 * m + 30
        value = float(points[0][1]) if t <= points[0][0] else float(points[-1][1])
        for (t0, e0), (t1, e1) in zip(points, points[1:]):
            if t0 < t <= t1:
                value = e0 + (e1 - e0) * (t - t0) / (t1 - t0) if t1 > t0 else float(e1)
                break
        out.append(_energy_char(value))
    return "".join(out)


def _set_rows(repo: check_repo.Repo, text: str) -> tuple[list[dict], list[str], list[str]]:
    """The set's tracks in order (artist, title, tempo, owner energy, block), the blocks'
    description and the `missing` lines found while reading."""
    by_path = {b.path: b for b in repo.blocks}
    rows: list[dict] = []
    blocks: list[str] = []
    missing: list[str] = []
    for block_id in check_repo.set_block_ids(text):
        block = by_path.get(f"blocks/{block_id}.md")
        if block is None:
            missing.append(f"block {block_id}: blocks/{block_id}.md does not exist")
            continue
        front = block.front or {}
        energy = front.get("energy")
        blocks.append(f"{block_id} ({front.get('function', '?')}"
                      + (f", e{energy[0]}-{energy[1]}" if isinstance(energy, list) and len(energy) == 2 else "") + ")")
        for (artist, title, tempo), (_, _, owner) in zip(set_timeline.block_tempos(block.text),
                                                          set_timeline.block_energies(block.text)):
            rows.append({"artist": artist, "title": title, "tempo": tempo, "owner": owner, "block": block_id,
                         "name": f"{artist} — {title}"})
    return rows, blocks, missing


def render_brief(repo: check_repo.Repo, set_rel: str) -> str:
    """The brief of the set at `set_rel` (a repo-relative path), module docstring. Raises
    `OSError` or `UnicodeDecodeError` when the set cannot be read."""
    text = check_repo.read_text(repo.root / set_rel)
    front = check_repo._split_block(set_rel, text, []).front
    arc = front.get("arc") if isinstance(front, dict) else None
    rows, blocks, missing = _set_rows(repo, text)
    for r in rows:
        r["path"], r["map"], problem = _find_map(repo, r["artist"], r["title"])
        if r["owner"] is None:
            r["owner"] = _pool_energy(repo, r["artist"], r["title"])
        if r["map"] is None:
            why = "no map" if r["path"] is None else f"invalid map {r['path']}: {problem}"
            missing.append(f"{r['name']}: {why}; the clock leaves it out")
    have = [r for r in rows if r["map"] is not None]
    clock = show_views.set_clock([r["map"] for r in have], [r["tempo"] for r in have])
    for r, tc in zip(have, clock.tracks):
        r["tc"] = tc
    night = [b for r in have
             for b in show_energy.music_bars(r["map"])[max(r["tc"].leg[0] - 1, 0):max(r["tc"].leg[1], 0)]]

    out = ["night",
           f"  {show_views.clock_text(clock.total_s)} · {len(rows)} tracks · arc {arc if isinstance(arc, str) else 'none'}",
           "  blocks: " + (", ".join(blocks) or "none")]
    if clock.tracks:
        tempi = [t for tc in clock.tracks for t in tc.tempo]
        out.append(f"  tempo: {clock.tracks[0].tempo[0]:g} -> {clock.tracks[-1].tempo[1]:g} BPM "
                   f"(lowest {min(tempi):g}, highest {max(tempi):g})")
    out += ["", "tracks"]
    music = []
    for n, r in enumerate(rows, 1):
        head = f"  {n}. {r['name']} · {r['block']}"
        tc = r.get("tc")
        if tc is None:
            out += [head, "     no clock (no usable map)"]
            continue
        data = r["map"]
        lo, hi = max(tc.leg[0] - 1, 0), max(tc.leg[1], 0)
        leg = show_energy.music_bars(data)[lo:hi]
        e_music = show_energy.music_energy(leg, night) if leg else []
        mean = sum(e_music) / len(e_music) if e_music else None
        p90 = float(np.percentile(e_music, 90)) if e_music else None
        music.append((r["name"], r["owner"], mean))
        b, g = show_views._cue_bar(data, "B"), show_views._cue_bar(data, "G")
        mix = f"{set_timeline.last_bar(data) - g + 1} bars" if g is not None else "-"
        letters = ["."] * data["bars"]
        for s in data["sections"]:
            for bar in range(s["bars"][0], s["bars"][1] + 1):
                letters[bar - 1] = nextrack_map.SECTION_LETTERS[s["kind"]]
        vocals = show_views._bar_text(data, "vocals")[lo:hi]
        share = sum(1 for c in vocals if show_views._digit(c) >= VOCAL_LEVEL) / len(vocals) if vocals else None
        interim = any(x.loudness is None for x in leg)
        out.append(head)
        out.append(f"     enters {show_views.clock_text(tc.start_s)} · leg {_minutes(tc.span_s(*tc.leg))} min · "
                   f"bars {tc.leg[0]}-{tc.leg[1]} · B {b if b is not None else '-'} · G {g if g is not None else '-'} · "
                   f"mix {mix} · {tc.tempo[0]:g}->{tc.tempo[1]:g} BPM")
        out.append(f"     owner {'e' + str(r['owner']) if r['owner'] is not None else '-'} · E_music mean "
                   + (f"{mean:.1f} p90 {p90:.1f}" if mean is not None else "-") + (" (interim)" if interim else "")
                   + f" · vocals {'-' if share is None else f'{round(100 * share)}%'}")
        out.append("     " + "".join(letters[lo:hi]))
        if interim:
            missing.append(f"{r['name']}: v1 map (no mix); its E_music is interim")
        if tc.index > 0 and b is None:
            missing.append(f"{r['name']}: no hot cue B; it enters at bar 1")
        if tc.index < len(have) - 1 and g is None:
            missing.append(f"{r['name']}: no hot cue G; it plays to the end")

    out += ["", "drops"]
    ranked = sorted(show_analysis.map_drops([r["map"] for r in have], clock),
                    key=lambda f: (-f["salience"], clock.tracks[f["index"]].at(f["d"])))
    for rank, f in enumerate(ranked, 1):
        r, tc = have[f["index"]], clock.tracks[f["index"]]
        out.append(f"  {rank}. {show_views.clock_text(tc.at(f['d']))} · {r['title']} bar {f['d']} · "
                   f"S {f['salience']:.2f}" + (" · main" if f["main"] else ""))
    if not ranked:
        out.append("  none")
    points = [(tc.start_s, r["owner"]) for r, tc in zip(have, clock.tracks) if r["owner"] is not None]
    out += ["", "target", "  one character per minute from 0:00 (1-9, X is 10)",
            f"  {_target_strip(points, clock.total_s)}", "", "labels"]
    out += [f"  {q}" for q in show_analysis._label_questions(music)] or ["  none"]
    out += ["", "missing"]
    out += [f"  {m}" for m in missing] or ["  none"]
    return "\n".join(out) + "\n"
