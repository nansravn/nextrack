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
from showdata import FILE_1, two_track_show


def compiled(src, inp):
    show, findings = compile_show(src, inp)
    assert findings == [], findings
    return show


def v2(data, loudness="5" * 32, bass="0" * 32):
    data["map_version"] = 2
    data["mix"] = {"loudness": loudness, "brightness": "5" * 32}
    data["voices"]["bass"]["bars"] = bass
    return data


def night(music=lambda b: 5, light=lambda b: 5, tweak=None, bare=False, edit=None):
    """The two-track show with hand-made series: `music(bar)` and `light(bar)` fill every
    track's window (a light of None is unknown). `bare` takes the cues, the bridge and the
    handover out, for a map whose sections the cues do not fit."""
    src, inp = two_track_show()
    if edit:
        edit(src)
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


# ---------------------------------------------------------------- variety --


def test_the_longest_static_run_crosses_a_bridge():
    def edit(src):
        src.track_files[FILE_1]["cues"][2]["look"] = "pulso"      # the last drop plays the handover's look
    show, clock = night(edit=edit)
    run = next(r for r in sa.variety(show, clock).static_runs if r.index == 0 and r.bars[0] == 21)
    assert run.bars == (21, 8) and run.seconds == pytest.approx(16.0) and run.music == "drop+intro"


def _bar(sig, start):
    return sa._LegBar(0, int(start), float(start), 1.0, {}, sig)


def test_window_variety_is_0_for_one_signature():
    bars = [_bar(("a",), t) for t in range(300)]
    assert sa._window(bars, 300.0) == [0, 0, 0, 0, 0]
    mixed = [_bar(("a",) if t < 120 else ("b",), t) for t in range(300)]
    assert sa._window(mixed, 300.0)[2] == 9          # minute 2: the window 0-240 s holds both in halves


def test_dominance_marks_declared_values():
    def edit(src):
        src.show["identity"] = {"signatures": [{"name": "sangue", "intent": "O vermelho.",
                                                "is": {"movers.colour": ["vermelho"]}}]}
    show, clock = night(edit=edit)
    dominance = sa.variety(show, clock).dominance
    assert dominance["movers.colour"].value == "vermelho" and dominance["movers.colour"].declared
    assert not dominance["look"].declared and "auto" not in {d.value for d in dominance.values()}


def test_identical_tracks_have_similarity_1():
    v = {("look", "pulso"): 0.6, ("aim", "Up"): 0.4}
    assert sa._cosine(v, dict(v)) == pytest.approx(1.0)
    assert sa._cosine(v, {("look", "x"): 1.0}) == pytest.approx(0.0)
    assert sa._cosine(v, {}) is None
    show, clock = night()
    assert all(0.0 <= c <= 1.0 for _, c in sa.variety(show, clock).similarity)


def test_similarity_leaves_the_bridge_out():
    show, clock = night()
    bars = sa._leg_bars(show, clock)
    assert [(b.index, b.bar) for b in bars if b.bridge] == [(1, 5), (1, 6), (1, 7), (1, 8)]

    def vector(i, keep):
        mine = [b for b in bars if b.index == i and b.values is not None and keep(b)]
        return sa._shares(mine, sum(b.seconds for b in mine))
    without = sa._cosine(vector(0, lambda b: not b.bridge), vector(1, lambda b: not b.bridge))
    with_bridge = sa._cosine(vector(0, lambda b: True), vector(1, lambda b: True))
    assert without != pytest.approx(with_bridge)
    assert sa.variety(show, clock).similarity == [(0, pytest.approx(without))]


def test_phrase_share_counts_changes_on_4_bar_lines():
    show, clock = night()
    changes = show.cache["energy"][0].changes
    assert sa.variety(show, clock).phrase_share is None
    for bar in (9, 10, 13, 15):         # the map section starts at 9: 9 and 13 are on its 4-bar lines
        changes[bar - 1] = 1
    assert sa.variety(show, clock).phrase_share == pytest.approx(0.5)


# -------------------------------------------------------------------- arc --


def _arc_tracks(energies, means, p90s=None):
    p90s = p90s or means
    return [sa.ArcTrack(i, f"A — T{i}", e, m, p, None, None, {}) for i, (e, m, p) in enumerate(zip(energies, means, p90s))]


def test_arc_rho_follows_the_owner_energy():
    rho, rho90, *_ = sa._arc_stats(_arc_tracks([6, 8, 9], [2, 4, 7]))
    assert rho == pytest.approx(1.0) and rho90 == pytest.approx(1.0)
    assert sa._arc_stats(_arc_tracks([6, 9], [2, 7]))[0] is None            # two pairs: no correlation
    assert sa._arc_stats(_arc_tracks([6, 8, 9], [5, 5, 5]))[0] is None


def test_headroom_reads_the_peak_before_the_peak_track():
    tracks = _arc_tracks([6, 9, 7], [3, 8, 4], p90s=[4, 8, 5])
    assert sa._arc_stats(tracks)[2] == pytest.approx(0.5)
    assert sa._arc_stats(_arc_tracks([9, 6], [3, 4]))[2] is None            # the peak track opens the night
    assert sa._arc_stats(_arc_tracks([6, 9], [0, 0]))[2] is None            # a max p90 of 0


def test_the_staircase_breaks_when_a_lower_energy_outshines_the_past():
    assert sa._arc_stats(_arc_tracks([7, 5, 9], [4, 6, 8]))[3] == [1]
    assert sa._arc_stats(_arc_tracks([5, 7, 9], [4, 6, 8]))[3] == []


def test_a_flat_step_is_flagged_when_energy_rises_and_light_does_not():
    assert sa._arc_stats(_arc_tracks([5, 7], [4.0, 4.5]))[4] == [(1, "flat")]
    assert sa._arc_stats(_arc_tracks([6, 6], [2.0, 5.0]))[4] == [(1, "jump")]
    assert sa._arc_stats(_arc_tracks([5, 7], [3.0, 6.0]))[4] == []


def test_a_top_drop_without_a_breather_is_listed():
    def tweak(data):
        data["mix"]["loudness"] = "5" * 20 + "9" * 12          # the last drop of each track rises
    show, clock = night(light=lambda b: 1 if b <= 20 else 9, tweak=tweak)
    show.cache["energy"][1].light = [None] * len(show.cache["energy"][1].light)
    assert sa.arc(show, clock).breathers == [(0, 21)]
    calm, clock = night(tweak=tweak)
    assert sa.arc(calm, clock).breathers == []


def test_the_label_check_names_a_track_three_ranks_off():
    rows = [("X — A", 9, 1.0), ("X — B", 8, 8.0), ("X — C", 7, 7.0), ("X — D", 6, 6.0)]
    assert sa._label_questions(rows) == ["A: owner energy e9 ranks 1, measured music ranks 4: check the label"]
    assert sa._label_questions([("X — A", None, 1.0)]) == []


def test_the_arc_reads_the_owner_energies_of_the_show():
    show, clock = night()
    show.energies = {t.track: e for t, e in zip(show.tracks, (6, 8))}
    arc = sa.arc(show, clock)
    assert [t.energy for t in arc.tracks] == [6, 8] and arc.target == [(0.0, 6), (clock.tracks[1].start_s, 8)]
    assert arc.tracks[0].mean == 5.0 and arc.tracks[0].rare["strobe"] == 1 and 0.0 <= arc.tracks[0].warm <= 1.0


# --------------------------------------------------------------- identity --


def test_identity_measures_a_declared_signature():
    def edit(src):
        src.show["identity"] = {"arc": "waves", "signatures": [
            {"name": "azul-espaco", "intent": "O azul é o espaço.", "is": {"movers.colour": ["azul"]},
             "share": {"min": 0.9}}]}
    show, clock = night(edit=edit)
    result = sa.identity(show, clock)
    azul = sv.night_summary(show, clock, show.room)["colours"]["movers"]["azul"]
    check = result.signatures[0]
    assert result.arc == "waves" and check.name == "azul-espaco"
    assert check.share == pytest.approx(azul / clock.total_s) and check.share > 0
    assert check.min == 0.9 and check.max is None and not check.ok
    assert sum(o[3] for o in check.occurrences) == pytest.approx(azul)
    assert result.undeclared["movers.colour"][0] != "azul"


def test_a_show_without_identity_declares_nothing():
    show, clock = night()
    result = sa.identity(show, clock)
    assert result.arc is None and result.signatures == [] and "look" in result.undeclared


def test_analyse_is_cached():
    show, _ = night()
    first = sa.analyse(show)
    assert sa.analyse(show) is first
    assert len(first.follows) == 2 and first.arc is not None and first.identity is not None
