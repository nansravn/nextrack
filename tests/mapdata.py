"""A valid musical map for tests: `good_map(bars)` and the helper to chunk step strings."""
import copy

VOICES = ("vocals", "kick", "perc", "bass", "other")
GUID = "0123ABCD-0123-4567-89AB-0123456789AB"


def chunks(text: str, size: int = 128) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def good_map(bars: int = 4, **overrides) -> dict:
    """A valid map of `bars` bars for the pool track `Pedro Sampaio — Dançarina`.
    `overrides` replace top-level keys."""
    n = bars * 16
    voices = {}
    for voice in VOICES:
        entry = {"bars": "5" * bars, "entries": [1], "exits": [bars]}
        if voice == "bass":
            entry = {"bars": "5" * bars}
        if voice in ("perc", "other"):
            entry = {"bars": "5" * bars, "balance": "c" * bars}
        voices[voice] = entry
    half = max(bars // 2, 1)
    sections = [{"bars": [1, half], "kind": "groove"}]
    if half < bars:
        sections.append({"bars": [half + 1, bars], "kind": "drop"})
    data = {
        "map_version": 1,
        "track": "Pedro Sampaio — Dançarina",
        "soundswitch": GUID,
        "audio": {"sha256": "3f9c1a2b4d5e", "ms": 8000},
        "grid": {"bpm": 120.0, "downbeat": "0:00.061", "anchors": [[61, 120.0]], "offset_ms": -5},
        "separator": "htdemucs",
        "bars": bars,
        "hot_cues": {"A": "1.1", "B": f"{bars}.1"},
        "voices": voices,
        "steps": {v: chunks("5" * n) for v in VOICES},
        "onsets": {"kick": chunks("9..." * (n // 4)), "perc": chunks("." * n)},
        "register": chunks(("." * 15 + "5") * bars),
        "phrases": [{"from": "1.1", "to": f"{bars}.4", "register": "mid", "level": 8}],
        "sections": sections,
        "drops": [{"bar": bars, "db": 12.5}],
        "silences": [[1, 1]],
    }
    data.update(copy.deepcopy(overrides))
    return data


def cue_ms(bar: int, beat: int = 1) -> int:
    """Milliseconds of a bar.beat on the 120 BPM grid that starts at 0 ms (`timeline_map`)."""
    return round(((bar - 1) * 4 + beat - 1) * 500)


def timeline_map(bars: int, *, sections=None, drops=(), silences=(), hot=None) -> dict:
    """A valid map of `bars` bars at 120 BPM from 0 ms (bar n starts at (n - 1) * 2000 ms) with
    the given sections, `(bar, db)` drops, silences and stored hot cues."""
    d = good_map(bars)
    d["grid"]["anchors"] = [[0, 120.0]]
    d["sections"] = sections or [{"bars": [1, bars], "kind": "groove"}]
    d["drops"] = [{"bar": b, "db": db} for b, db in drops]
    d["silences"] = [list(s) for s in silences]
    d["hot_cues"] = hot
    return d
