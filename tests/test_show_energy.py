"""Energy per bar (show_energy.py): normalisation, music energy, light measures from the
compiler's samples, change events and the night's series.

The base show is `two_track_show` at 120 BPM: Dançarina plays the autoscript in bars 1-8 and
chegada (look respiracao, every layer set) from bar 9."""
import pytest
from mapdata import good_map

import show_energy as se
import show_views as sv
import show_zoom as sz
from show_language import compile_show
from showdata import FILE_1, FILE_2, show_map, two_track_show

STEPS = 16


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return show


def step(movers=(0.0, 0.0), units=(0.0, 0.0), coverage=(1.0, 1.0), white=0.0, strobe=False, hue=0.0):
    return sz.StepLight(0, tuple(movers), tuple(units), tuple(coverage), white, strobe, hue)


def bar_of(*steps):
    """16 samples: the given steps first, dark steps after."""
    return list(steps) + [step()] * (STEPS - len(steps))


# --------------------------------------------------------------- normalise --


def test_normalise_clips_to_the_scope_percentiles():
    scope = list(range(101))                              # p5 = 5, p95 = 95
    assert se.normalise([5, 50, 95, -10, 200], scope) == pytest.approx([0.0, 0.5, 1.0, 0.0, 1.0])


def test_a_constant_scope_normalises_to_a_half():
    assert se.normalise([3, 4, 9], [4, 4, 4]) == [0.5, 0.5, 0.5]
    assert se.normalise([3], []) == [0.5]


# ------------------------------------------------------------------- music --


def _two_level_map():
    data = good_map(16, version=2)
    data["mix"] = {"loudness": "2" * 8 + "9" * 8, "brightness": "5" * 16}
    for voice, entry in data["voices"].items():
        entry["bars"] = ("6" + "0" * 0) * 0 + ("6" if voice == "kick" else "0") * 8 + ("7" if voice != "bass" else "0") * 8
    data["voices"]["bass"]["bars"] = "0" * 8 + "7" * 8
    data["voices"]["perc"]["bars"] = "0" * 8 + "7" * 8
    return data


def test_music_energy_rises_with_loudness_and_texture():
    bars = se.music_bars(_two_level_map())
    assert [b.texture for b in bars] == [1] * 8 + [5] * 8
    energy = se.music_energy(bars, bars)
    assert min(energy[8:]) > max(energy[:8])


def test_a_v1_map_uses_the_interim_formula_and_says_so():
    data = good_map(16)                                   # version 1: no mix
    bars = se.music_bars(data)
    assert all(b.loudness is None and b.brightness is None for b in bars)
    # density 0.25 and texture 0 everywhere: a constant scope, so 0.5 x 0.5 + 0.5 x 0.5 -> 9 / 2
    assert se.music_energy(bars, bars) == [5] * 16
    src, inp = two_track_show()
    show = compiled(src, inp)
    assert [t.interim for t in se.night_energy(show, sv.build_clock(show))] == [True, True]


def test_music_bars_read_density_and_the_mix():
    data = good_map(2, version=2)
    data["mix"] = {"loudness": "37", "brightness": "05"}
    data["onsets"]["perc"] = ["2" * 16 + "3" * 16]       # strength 2 is below the floor
    bars = se.music_bars(data)
    assert [(b.loudness, b.brightness) for b in bars] == [(3, 0), (7, 5)]
    assert bars[0].density == 0.25 and bars[1].density == 1.0


# ------------------------------------------------------------------- light --


def test_light_activity_sees_rate():
    def activity(rate):
        src, inp = two_track_show()
        entry = src.track_files[FILE_1]["cues"][0]
        entry["look"] = {"movers": {"move": "hold", "colour": "azul", "position": "Crossed Over"},
                         "matrix": {"draw": "columns", "rate": rate, "colour": "azul"},
                         "hue": {"state": "pulse", "colour": "vermelho"}}
        entry.pop("with", None)
        track = compiled(src, inp).tracks[0]
        bars = se.light_bars(sz.sample_light(track, 9, 16, None, None))
        assert all(b.activity is not None for b in bars)
        return sum(b.activity for b in bars)

    assert activity("1/16") > activity("1bar")


def test_strobe_and_white_enter_the_light():
    dark = se.light_bars(bar_of())[0]
    white = se.light_bars(bar_of(*[step(white=1.0)] * 8), step())[0]
    strobe = se.light_bars(bar_of(step(strobe=True), step(), step(strobe=True)), step())[0]
    assert dark == se.BarLight(0.0, 0.0)
    assert white.brightness == pytest.approx(0.10 * 0.5) and white.activity == pytest.approx(0.10 / 16)
    assert strobe.brightness == pytest.approx(0.05 * 2 / 16) and strobe.activity == pytest.approx(0.05 * 2 / 16)


def test_the_first_step_compares_with_the_previous_bar():
    lit = [step(hue=1.0)] * STEPS
    assert se.light_bars(lit)[0].activity == 0.0                       # nothing before: no rise
    assert se.light_bars(lit, before=step())[0].activity == pytest.approx(0.15 / 16)
    assert se.light_bars(lit, before=step(hue=1.0))[0].activity == 0.0


def test_an_auto_layer_makes_the_bar_unknown():
    auto = bar_of(step(), step(hue=None))
    assert se.light_bars(auto)[0] == se.BarLight(None, None)
    assert se.light_bars(bar_of(step(movers=(None, None))))[0].brightness is None
    scope = se.light_bars(bar_of(*[step(hue=1.0)] * 8) + bar_of())
    assert se.light_energy(se.light_bars(auto), scope) == [None]


def test_light_energy_spans_the_scope():
    bars = se.light_bars(bar_of(*[step(hue=1.0)] * 8) + bar_of(*[step(hue=0.2)] * 2) + bar_of(), step())
    energy = se.light_energy(bars, bars)
    assert energy[0] > energy[1] >= energy[2] == 0 and energy[0] == 9


# ----------------------------------------------------------------- changes --


def test_changes_count_the_dimensions_that_change():
    src, inp = two_track_show()
    show = compiled(src, inp)
    first = se.night_energy(show, sv.build_clock(show))[0]
    assert first.at("changes", 1) == 0
    assert first.at("changes", 8) == 0
    assert first.at("changes", 9) == len(se.CHANGE_DIMENSIONS)         # autoscript -> chegada
    assert first.at("changes", 10) == 0
    assert first.at("changes", 999) is None


def test_signature_of_no_section_is_all_auto():
    assert se.signature(None, None, {}) == tuple(("auto",) for _ in se.DIMENSIONS)
    assert se.CHANGE_DIMENSIONS == se.DIMENSIONS[2:] and len(se.CHANGE_DIMENSIONS) == 9


def test_dimension_values_name_colours_and_looks():
    src, inp = two_track_show()
    show = compiled(src, inp)
    section = next(s for s in show.tracks[0].sections if s.origin.look == "respiracao")
    values = se.dimension_values(section, None, {"#0A2CFF": "azul"})
    assert values["look"] == ("respiracao",) and values["gesture"] == ("none",)
    assert values["movers.colour"] == ("azul",) and values["movers.move"] == ("sweep",)
    assert values["matrix.rate"] == ("1bar",)
    assert se.signature(section, None, {}) == se.signature(section, None, {})


# ------------------------------------------------------------------- night --


def test_night_energy_is_cached_on_the_show():
    src, inp = two_track_show()
    show = compiled(src, inp)
    clock = sv.build_clock(show)
    energy = se.night_energy(show, clock)
    assert show.cache["energy"] is energy and se.night_energy(show, clock) is energy
    assert [t.track for t in energy] == [t.track for t in show.tracks]
    first = energy[0]
    assert first.first == 1 and len(first.music) == len(first.light) == len(first.changes) == 32
    assert first.at("light", 1) is None and first.at("light", 9) is not None   # the autoscript is unknown
    assert energy[1].first == clock.tracks[1].sounding[0]


def test_a_v2_map_is_not_interim():
    src, inp = two_track_show()
    for data in inp.maps.values():
        data["map_version"] = 2
        data["mix"] = {"loudness": "5" * 32, "brightness": "5" * 32}
    show = compiled(src, inp)
    assert [t.interim for t in se.night_energy(show, sv.build_clock(show))] == [False, False]
    assert show_map(32)["bars"] == 32 and FILE_2
