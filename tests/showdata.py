"""Shared synthetic data for the show language tests: a valid map with sections and hot cues."""
from mapdata import good_map

PALETTE = {"azul": "#0A2CFF", "vermelho": "#FF0A2A"}
DEFAULT_SECTIONS = [(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"), (21, 32, "drop")]


def show_map(bars: int = 32, sections: list[tuple[int, int, str]] | None = None,
             hot_cues: dict | None = None, track: str = "Pedro Sampaio — Dançarina",
             **overrides) -> dict:
    """A valid map of `bars` bars. `drops` is derived from the sections of kind `drop`."""
    sections = DEFAULT_SECTIONS if sections is None else sections
    if hot_cues is None:
        hot_cues = {"A": "1.1", "B": "5.1", "G": "25.1"}
    data = good_map(bars, track=track)
    data["sections"] = [{"bars": [a, b], "kind": kind} for a, b, kind in sections]
    data["drops"] = [{"bar": a, "db": 12.5} for a, _, kind in sections if kind == "drop"]
    data["hot_cues"] = hot_cues
    data.update(overrides)
    return data
