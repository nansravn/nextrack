"""Follows, drops and builds (show_analysis.py) on synthetic shows.

The base show is `two_track_show` at 120 BPM: track 1 plays bars 1-24 (window 1-32), track 2
bars 5-32; both maps have drops at 9 and 21 and a 4-bar break (17-20) before the last drop.
Most tests set the energy series by hand in `show.cache` so each number is known; the
salience and freshness tests read the real series."""
import pytest

import show_analysis as sa
import show_energy as se
import show_views as sv
from show_language import compile_show
from showdata import two_track_show


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return show


def v2(data, loudness="5" * 32, bass="0" * 32):
    data["map_version"] = 2
    data["mix"] = {"loudness": loudness, "brightness": "5" * 32}
    data["voices"]["bass"]["bars"] = bass
    return data


def night(music=lambda b: 5, light=lambda b: 5, tweak=None, bare=False):
    """The two-track show with hand-made series: `music(bar)` and `light(bar)` fill every
    track's window (a light of None is unknown). `bare` takes the cues, the bridge and the
    handover out, for a map whose sections the cues do not fit."""
    src, inp = two_track_show()
    if bare:
        for entry in src.track_files.values():
            entry["cues"] = []
            entry.pop("handover", None)
        src.show.pop("handover", None)
        src.show.pop("bridge", None)
    for data in inp.maps.values():
        v2(data)
        if tweak:
            tweak(data)
    show = compiled(src, inp)
    clock = sv.build_clock(show)
    energy = []
    for i, (t, tc) in enumerate(zip(show.tracks, clock.tracks)):
        bars = range(tc.sounding[0], tc.sounding[1] + 1)
        energy.append(se.TrackEnergy(i, t.track, tc.sounding[0], [music(b) for b in bars], [music(b) for b in bars],
                                     [light(b) for b in bars], [light(b) for b in bars], [light(b) for b in bars],
                                     [0] * len(bars), False))
    show.cache["energy"] = energy
    show.cache["energy_key"] = tuple((c.leg, c.sounding) for c in clock.tracks)
    return show, clock


def stepped(b):
    return 1 if b < 9 else 8 if b < 21 else 3


# --------------------------------------------------------------- spearman --


def test_spearman_known_values():
    assert sa.spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert sa.spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert sa.spearman([1, 2, 3], [4, 4, 4]) is None
    assert sa.spearman([1, 2], [1, 2]) is None
    assert sa.spearman([1, 2, 2, 4], [1, 2, 2, 4]) == pytest.approx(1.0)       # ties share a rank


# ---------------------------------------------------------------- follows --


def test_a_light_that_rises_with_the_music_follows_it():
    show, clock = night(stepped, stepped)
    row = sa.follows(show, clock)[0]
    assert row.rho > 0.5
    assert row.missed == [] and row.agreement == 1.0 and row.lag == 0
    assert row.unknown_share == 0.0


def test_a_flat_light_misses_the_boundaries():
    show, clock = night(stepped, lambda b: 5)
    row = sa.follows(show, clock)[0]
    assert [b.bar for b in row.missed] == [9, 21]
    assert row.rho is None and row.agreement == 0.0
    assert row.missed[0].music == pytest.approx(7)


def test_a_light_that_jumps_alone_is_unmotivated():
    show, clock = night(lambda b: 5, lambda b: 1 if b < 9 else 8 if b < 21 else 5)
    row = sa.follows(show, clock)[0]
    assert [b.bar for b in row.unmotivated] == [9, 21]
    assert row.agreement is None and row.missed == []


def test_lag_reads_a_late_light():
    wave = [1, 7, 3, 9, 2, 8, 4, 6, 0, 5, 9, 1, 7, 2, 8, 3, 6, 0, 4, 9, 1, 5, 8, 2, 6, 3, 9, 0, 7, 4, 5, 2, 8]

    def music(b):
        return wave[b % len(wave)]

    show, clock = night(music, lambda b: music(b - 2))
    assert sa.follows(show, clock)[0].lag == 2
    show, clock = night(music, lambda b: music(b + 1))
    assert sa.follows(show, clock)[0].lag == -1


def test_a_track_all_autoscript_gives_none_not_a_crash():
    show, clock = night(stepped, lambda b: None)
    row = sa.follows(show, clock)[0]
    assert (row.rho, row.agreement, row.lag) == (None, None, None)
    assert row.missed == [] and row.unknown_share == 1.0
    assert all(d.contrast is None and d.response is None for d in sa.drops(show, clock))
    assert {b.into for b in sa.builds(show, clock)} == {"unknown"}


# ------------------------------------------------------------------ drops --


def test_drops_rank_by_salience():
    def tweak(data):
        data["mix"]["loudness"] = "2" * 8 + "5" * 12 + "9" * 12
        data["voices"]["bass"]["bars"] = "0" * 20 + "9" * 12
    show, clock = night(tweak=tweak)
    rows = sa.drops(show, clock)
    assert [r.rank for r in rows] == [1, 2, 3, 4]
    assert [r.salience for r in rows] == sorted((r.salience for r in rows), reverse=True)
    best = rows[0]
    assert best.bar == 21 and best.loud_rise == pytest.approx(4) and best.bass_return == pytest.approx(1.0)
    assert best.salience == pytest.approx(0.4 * 1 + 0.3 * 1 + 0.2 * 0 + 0.1)        # density is flat
    nine = next(r for r in rows if r.index == 0 and r.bar == 9)
    assert nine.loud_rise == pytest.approx(3) and nine.bass_return == 0 and nine.salience < best.salience


def test_the_last_drop_of_a_track_is_main():
    def tweak(data):
        data["mix"]["loudness"] = "2" * 8 + "9" * 12 + "5" * 12          # the biggest rise is the first drop
    show, clock = night(tweak=tweak)
    rows = {(r.index, r.bar): r for r in sa.drops(show, clock)}
    assert rows[(0, 9)].main and rows[(0, 21)].main                           # biggest, and last


def test_only_the_biggest_or_last_drop_is_main():
    def tweak(data):
        data["mix"]["loudness"] = "2" * 8 + "5" * 12 + "9" * 12
    show, clock = night(tweak=tweak)
    rows = {(r.index, r.bar): r for r in sa.drops(show, clock)}
    assert not rows[(0, 9)].main and rows[(0, 21)].main


def test_a_drop_with_a_dark_bar_before_has_positive_contrast():
    show, clock = night(lambda b: 5, lambda b: 0 if b < 9 else 6)
    row = next(r for r in sa.drops(show, clock) if r.index == 0 and r.bar == 9)
    assert row.contrast == pytest.approx(6)
    flat = next(r for r in sa.drops(show, clock) if r.index == 0 and r.bar == 21)
    assert flat.contrast == pytest.approx(0)


def test_contrast_at_a_legs_first_bar_reads_the_previous_track():
    src, inp = two_track_show()
    for data in inp.maps.values():
        v2(data)
        data["drops"] = [{"bar": 5, "db": 12.0}]                              # track 2 enters on 5
    show = compiled(src, inp)
    clock = sv.build_clock(show)
    assert clock.tracks[1].leg[0] == 5
    energy = [se.TrackEnergy(i, t.track, tc.sounding[0], [5] * (tc.sounding[1] - tc.sounding[0] + 1),
                             [5] * (tc.sounding[1] - tc.sounding[0] + 1), [2] * (tc.sounding[1] - tc.sounding[0] + 1),
                             [2] * 28, [2] * 28, [0] * 28, False)
              for i, (t, tc) in enumerate(zip(show.tracks, clock.tracks))]
    energy[1].light[0:4] = [8, 8, 8, 8]
    show.cache["energy"] = energy
    show.cache["energy_key"] = tuple((c.leg, c.sounding) for c in clock.tracks)
    row = next(r for r in sa.drops(show, clock) if r.index == 1)
    assert row.contrast == pytest.approx(8 - 2)                               # the 2 bars before are the previous track's


def test_freshness_is_low_for_a_repeated_look():
    src, inp = two_track_show()
    show = compiled(src, inp)
    clock = sv.build_clock(show)
    rows = {(r.index, r.bar): r for r in sa.drops(show, clock)}
    assert rows[(0, 9)].freshness == 1.0                                        # nothing came before it
    assert rows[(1, 21)].freshness < 0.5                                        # `pulso` again, ten minutes at most
    assert rows[(1, 21)].holder is not None and rows[(0, 9)].template[1] != rows[(0, 9)].template[0]


def test_response_adds_contrast_change_and_freshness():
    show, clock = night(lambda b: 5, lambda b: 0 if b < 9 else 8)
    show.cache["energy"][0].changes[8] = 9                                      # bar 9
    row = next(r for r in sa.drops(show, clock) if r.index == 0 and r.bar == 9)
    assert row.change == 9 and row.freshness == 1.0
    assert row.response == pytest.approx(0.5 + 0.25 + 0.25)


def test_top_and_agreement():
    show, clock = night(lambda b: 5, lambda b: 0 if b < 9 else 6)
    rows = sa.drops(show, clock)
    assert len(sa.top(rows, 2)) == 2 and sa.top(rows, 0.25) == rows[:1] and sa.top(rows, 0.01) == rows[:1]
    assert sa.top([], 3) == [] and sa.top([], 0.5) == []
    assert sa.drop_agreement(rows[:2]) is None


def test_a_night_with_no_drops_gives_no_rows():
    def tweak(data):
        data["drops"] = []
        data["sections"] = [{"bars": [1, 32], "kind": "groove"}]
    show, clock = night(tweak=tweak, bare=True)
    assert sa.drops(show, clock) == []
    assert sa.builds(show, clock) == []
    assert sa.drop_agreement([]) is None and sa.top([], 5) == []


# ----------------------------------------------------------------- builds --


@pytest.mark.parametrize("light, into", [
    (lambda b: 1 if b == 20 else 6, "dip"),
    (lambda b: 2 + (b - 17) if 17 <= b <= 20 else 2, "ramp"),
    (lambda b: 5, "flat"),
])
def test_a_build_reads_how_the_light_goes_into_the_drop(light, into):
    show, clock = night(lambda b: 5, light)
    row = next(b for b in sa.builds(show, clock) if b.index == 0)
    assert row.bars == (17, 20) and row.into == into


def test_a_build_into_a_dark_bar_reads_dip():
    show, clock = night(lambda b: 5, lambda b: 0 if b == 20 else 7)
    assert [b.into for b in sa.builds(show, clock)] == ["dip", "dip"]


def test_a_rising_music_has_a_positive_slope_and_the_light_slope_is_apart():
    def tweak(data):
        data["mix"]["loudness"] = "2" * 16 + "2468" + "9" * 12
    show, clock = night(lambda b: 5, lambda b: 2 if b < 17 else 2 + (b - 17), tweak)
    row = next(b for b in sa.builds(show, clock) if b.index == 0)
    assert row.music_slope > 0 and row.activity_slope == pytest.approx(1.0)
    assert row.brightness_slope == pytest.approx(1.0)


def test_a_build_section_counts_and_a_short_one_does_not():
    def tweak(data):
        data["sections"] = [{"bars": [1, 8], "kind": "intro"}, {"bars": [9, 14], "kind": "build"},
                            {"bars": [15, 16], "kind": "build"}, {"bars": [17, 32], "kind": "drop"}]
        data["drops"] = [{"bar": 17, "db": 12.0}]
    show, clock = night(tweak=tweak, bare=True)
    assert [b.bars for b in sa.builds(show, clock) if b.index == 0] == [(9, 14)]


def test_a_v1_map_still_gives_a_slope_from_the_density():
    src, inp = two_track_show()
    show = compiled(src, inp)
    clock = sv.build_clock(show)
    assert all(t.interim for t in se.night_energy(show, clock))
    rows = sa.builds(show, clock)
    assert [b.bars for b in rows] == [(17, 20), (17, 20)]
    assert all(isinstance(b.music_slope, float) for b in rows)
