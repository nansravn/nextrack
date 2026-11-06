"""Shared synthetic data for the show language tests: a valid map with sections and hot cues,
the source and inputs builders, and `two_track_show`, a valid and complete two-track show."""
from mapdata import good_map
from show_language import ShowInputs, ShowSource

PALETTE = {"azul": "#0A2CFF", "vermelho": "#FF0A2A"}
DEFAULT_SECTIONS = [(1, 8, "intro"), (9, 16, "drop"), (17, 20, "break"), (21, 32, "drop")]

TRACK_1 = "Pedro Sampaio — Dançarina"
TRACK_2 = "Chiclete com Banana — Voa Voa (Ao Vivo)"
FILE_1 = "pedro-sampaio-dancarina.yml"
FILE_2 = "chiclete-com-banana-voa-voa-ao-vivo.yml"
GUID_2 = "4567CDEF-4567-89AB-CDEF-456789ABCDEF"
# The mini repo's block alpha-festa, in its order (tests/conftest.py, MINI_REPO_FILES).
SET_TRACKS = [("Pedro Sampaio", "Dançarina"), ("Chiclete com Banana", "Voa Voa")]


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


def source(show: dict, tracks: dict[str, dict], folder: str = "lightshows/shows/teste") -> ShowSource:
    """A show folder in memory: `tracks` maps a file name to its data."""
    return ShowSource(show_id=folder.rstrip("/").rsplit("/", 1)[-1], folder=folder, show=show,
                      track_files=tracks)


def inputs(maps: dict[str, dict], set_tracks: list[tuple[str, str]]) -> ShowInputs:
    """What the repo gives a show: maps by slug and the set's `(artist, title)` order."""
    from check_repo import same_track  # deferred, as in conftest: tests collect without it

    return ShowInputs(maps=maps, set_tracks=set_tracks, set_problem=None, same_track=same_track)


def two_track_show() -> tuple[ShowSource, ShowInputs]:
    """A valid and complete two-track show on two `show_map`s (B 5, G 25, drops 9 and 21):
    a palette, two looks (one extends the other), a bridge, a handover with an accent and a
    moment, a `spiral` call, an arrival per track, accents and a `faster_from` anchor."""
    show = {
        "show_version": 1,
        "set": "sets/teste.md",
        "story": "Uma noite de teste: o azul abre, o vermelho fecha.",
        "palette": {"azul": "#0A2CFF", "vermelho": "#FF0A2A", "violeta": "#6A1CFF"},
        "looks": {
            "respiracao": {
                "movers": {"move": "sweep", "every": "2bar", "positions": ["Dance Floor Centre", "Crossed Over"],
                           "colour": "azul", "level": 0.7},
                "matrix": {"draw": "rows-up", "rate": "1bar", "colour": "azul", "mirror": True},
                "hue": {"state": "pulse", "colour": "vermelho"},
            },
            "pulso": {
                "extends": "respiracao",
                "movers": {"move": "blink", "every": "1/4", "colour": "vermelho", "positions": None,
                           "position": "Crossed Over"},
                "matrix": {"draw": "centre-out", "rate": "1/8", "colour": "vermelho"},
            },
        },
        "gesture_defaults": {"spiral": {"rates": ["1/2", "1/4"], "colours": ["azul", "violeta"],
                                        "aims": [["Crossed Over", "Up"], "Dance Floor Centre"]}},
        "bridge": {"name": "ponte", "intent": "Ponte: a mesma luz da música anterior, até a chegada."},
        "handover": {"name": "entrega", "intent": "Entrega: do G até o fim, o look que a próxima copia."},
    }
    first = {
        "track": TRACK_1,
        "story": "Dançarina abre a noite: o azul respira, a espiral gira e a virada acende o vermelho.",
        "cues": [
            {"at": "drop.1", "name": "chegada", "role": "arrival", "intent": "A chegada: o azul respira.",
             "look": "respiracao"},
            {"at": "break.1", "name": "espiral", "intent": "Espiral: os lados revezam cada vez mais rápido.",
             "gesture": "spiral", "with": {"bars": [2, 2]}},
            {"at": "drop.2", "name": "virada", "moment": "virada", "accents": ["white", "strobe"],
             "intent": "A virada: tudo em vermelho.",
             "look": {"movers": {"move": "blink", "every": "1/4", "colour": "vermelho", "position": "Crossed Over"},
                      "matrix": {"draw": "solid", "rate": "1/8", "colour": "vermelho"},
                      "hue": {"state": "pulse", "colour": "vermelho"}}},
        ],
        "handover": {"look": "pulso", "moment": "passagem", "accents": ["white"]},
    }
    second = {
        "track": TRACK_2,
        "story": "Voa Voa recebe a ponte e fecha a noite com o rolo de estrobo.",
        "budget": "Um rolo de estrobo no último drop.",
        "cues": [
            {"at": "drop.1", "name": "chegada", "role": "arrival", "look": "pulso",
             "with": {"matrix": {"draw": "zigzag"}}},
            {"at": "break.1", "name": "subida", "look": "respiracao",
             "with": {"movers": {"move": "pingpong", "every": "1/2", "faster_from": "drop.2 - 2",
                                 "faster_every": "1/4", "positions": None, "position": "Up", "level": None}}},
            {"at": "drop.2", "name": "final", "moment": "final", "accents": ["strobe-roll"], "look": "pulso"},
        ],
    }
    maps = {FILE_1[:-4]: show_map(), FILE_2[:-4]: show_map(track=TRACK_2, soundswitch=GUID_2)}
    return source(show, {FILE_1: first, FILE_2: second}), inputs(maps, list(SET_TRACKS))


def put_show(repo) -> tuple[ShowSource, ShowInputs]:
    """Write `two_track_show()` into a mini repo: the set file, the two maps, the show folder
    and the generated choreographies. `check` on the result reports nothing."""
    import yaml

    import musical_map
    from show_language import compile_show, emit_choreography

    src, inp = two_track_show()
    repo.write("sets/teste.md", "# Teste\n\n## Program\n1. 0:00 · [Alpha Festa](../blocks/alpha-festa.md)\n")
    for slug_, data in inp.maps.items():
        repo.write(f"lightshows/maps/{slug_}.yml", musical_map.dump_map(data))

    def dump(data):
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    repo.write("lightshows/shows/teste/show.yml", dump(src.show))
    for name, data in src.track_files.items():
        repo.write(f"lightshows/shows/teste/{name}", dump(data))
    compiled, found = compile_show(src, inp)
    assert compiled is not None, found
    for track in compiled.tracks:
        repo.write(f"lightshows/tracks/{track.slug}.yml", emit_choreography(track.choreography, src.folder))
    return src, inp
