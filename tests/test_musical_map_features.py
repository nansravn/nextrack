import yaml
import numpy as np

import musical_map as mm
from soundswitch_format import Grid
from synth import SR, clicks, db, glide, noise_burst, pan, place, real_kick, silence, tone


def test_step_edges_follow_the_grid():
    g = Grid([(500, 120.0)])
    audio_ms = 500 + 4 * 2000 + 700
    assert g.bar_at(audio_ms - 1) == 5
    e = mm.step_edges_ms(g, audio_ms)
    assert len(e) == 81
    assert e[0] == 500 and e[16] == 2500 and e[-1] == 9200


def test_step_edges_with_two_anchors():
    g = Grid([(0, 120.0), (4000, 60.0)])
    e = mm.step_edges_ms(g, 12000)
    assert e[32] == 4000 and e[48] == 8000


def test_drums_split_into_kick_and_perc():
    beat = 500
    parts = []
    for i in range(8):
        parts.append((i * beat, tone(60, 200, amp=0.5)))
        parts.append((i * beat + 250, noise_burst(200, amp=0.3, seed=i, low_hz=4000, high_hz=8000)))
    drums = place(8 * beat, parts)
    z = silence(4000)
    out = mm.voices_from_stems({"vocals": z, "drums": drums, "bass": z, "other": z}, SR)
    assert tuple(out) == mm.VOICES
    assert all(v.shape == (len(drums), 2) and v.dtype == np.float32 for v in out.values())
    edges = np.array([i * 250 for i in range(17)])
    for voice, on in (("kick", 0), ("perc", 1)):
        d = mm.rms_db(out[voice], SR, edges)
        assert d[on::2].min() > d[1 - on::2].max() + 20


def test_mono_input_is_two_equal_channels():
    z = silence(4000)
    out = mm.voices_from_stems({"vocals": tone(440, 4000), "drums": z, "bass": z, "other": z}, SR)
    assert out["vocals"].shape[1] == 2
    assert np.array_equal(out["vocals"][:, 0], out["vocals"][:, 1])
    assert mm.balance_letters(out["vocals"], SR, np.array([0, 2000, 4000])) == "cc"


def _voice_bars():
    x = np.concatenate([silence(4 * 2000), tone(440, 4 * 2000, amp=0.5)])
    return x, np.arange(9) * 2000


def test_levels_read_silence_then_loud():
    x, edges = _voice_bars()
    d = mm.rms_db(x, SR, edges)
    loud = mm.loud_db(d)
    assert mm.level_digits(d, loud, loud) == "00009999"


def test_bleed_reads_silent():
    x, edges = _voice_bars()
    d = mm.rms_db(x, SR, edges)
    loud = mm.loud_db(d)
    assert mm.level_digits(d, loud, loud + 40) == "0" * 8


def test_rms_db_silence_and_empty():
    d = mm.rms_db(silence(1000), SR, np.array([0, 500, 500, 1000]))
    assert list(d) == [-120, -120, -120]


def test_level_steps_of_three_db():
    d = np.array([0.0, -3.0, -6.0, -26.0, -27.0, -120.0])
    assert mm.level_digits(d, 0.0, 0.0) == "987100"


def test_entries_and_exits():
    assert mm.entries_exits("0099990000990") == ([3, 11], [6, 12])
    assert mm.entries_exits("9999") == ([1], [4])


def test_balance():
    x = tone(440, 4000)
    edges = np.array([0, 2000, 4000])
    assert mm.balance_letters(pan(x, 1, 0), SR, edges) == "LL"
    assert mm.balance_letters(pan(x, 1, db(-3)), SR, edges) == "ll"
    assert mm.balance_letters(pan(x, db(-3), 1), SR, edges) == "rr"
    assert mm.balance_letters(pan(x, 0, 1), SR, edges) == "RR"
    assert mm.balance_letters(pan(x), SR, edges) == "cc"
    assert mm.balance_letters(pan(silence(4000)), SR, edges) == "cc"


def test_entries_and_exits_with_ramps_and_fades():
    assert mm.entries_exits("0049") == ([4], [4])
    assert mm.entries_exits("94100") == ([1], [1])
    assert mm.entries_exits("9300") == ([1], [1])
    assert mm.entries_exits("0000") == ([], [])


def test_rms_db_absolute_scale():
    d = mm.rms_db(tone(440, 2000, amp=0.5), SR, np.array([0, 1000, 1000, 2000]))
    assert abs(d[0] - (-9.03)) < 0.1 and d[1] == -120 and abs(d[2] - (-9.03)) < 0.1


def test_out_of_phase_channels_do_not_cancel():
    x = tone(440, 1000)
    d = mm.rms_db(np.stack([x, -x], axis=1), SR, np.array([0, 1000]))
    assert abs(d[0] - (-9.03)) < 0.1


def test_loud_db_ignores_silence():
    assert mm.loud_db(np.array([-120.0, -120.0])) == -120
    assert mm.loud_db(np.array([-120.0, -10.0, -10.0])) == -10


def test_step_edges_never_decrease_past_the_end():
    e = mm.step_edges_ms(Grid([(0, 120.0)]), 2500)
    assert (np.diff(e) >= 0).all() and e[-1] == 2500


def test_a_300hz_tone_is_perc_not_kick():
    z = silence(2000)
    out = mm.voices_from_stems({"vocals": z, "drums": tone(300, 2000), "bass": z, "other": z}, SR)
    edges = np.array([0, 2000])
    assert mm.rms_db(out["perc"], SR, edges)[0] > mm.rms_db(out["kick"], SR, edges)[0] + 30


def test_29_db_under_the_mix_is_not_bleed():
    d = np.array([-10.0])
    assert mm.level_digits(d, -10.0, 19.0) == "9"
    assert mm.level_digits(d, -10.0, 21.0) == "0"


def test_balance_boundaries():
    x = tone(440, 1000)
    edges = np.array([0, 1000])
    for gain, letter in ((2, "l"), (6, "L"), (-2, "r"), (-6, "R")):
        left, right = (1.0, db(-gain)) if gain > 0 else (db(gain), 1.0)
        assert mm.balance_letters(pan(x, left, right), SR, edges) == letter
    assert mm.balance_letters(pan(x, 1, db(-1.9)), SR, edges) == "c"


def test_onsets_on_every_beat():
    g = Grid([(0, 120.0)])
    ms = 4000
    beats = [i * 500 for i in range(8)]
    x = clicks(beats, ms)
    digits, times = mm.onset_digits(x, SR, mm.step_edges_ms(g, ms))
    assert digits == "9...9...9...9...9...9...9...9..."
    assert len(times) == 8
    assert all(abs(t - b) <= 5 for t, b in zip(times, beats))


def test_onset_strength_order():
    g = Grid([(0, 120.0)])
    x = clicks([0], 2000) + clicks([500], 2000, amp=0.9 * db(-12))
    digits, _ = mm.onset_digits(x, SR, mm.step_edges_ms(g, 2000))
    assert digits[0] == "9" and digits[4] != "." and digits[0] > digits[4]


def test_register_rises_with_pitch():
    g = Grid([(0, 120.0)])
    ms = 4000
    x = np.concatenate([glide(150, 600, ms), silence(500)])
    edges = mm.step_edges_ms(g, ms + 500)
    levels = "9" * 32 + "0" * (len(edges) - 1 - 32)
    reg = mm.register_digits(x, SR, edges, levels)
    assert len(reg) == len(levels)
    assert set(reg[32:]) == {"."}
    d = [int(c) for c in reg[:32]]
    assert all(b >= a - 1 for a, b in zip(d, d[1:]))
    assert d[0] <= 2 and d[-1] >= 7


def test_phrase_gap_shorter_than_a_beat_does_not_split():
    g = Grid([(0, 120.0)])
    levels = "7" * 14 + "00" + "7" * 16
    reg = "5" * 14 + ".." + "5" * 16
    out = mm.phrases(levels, reg)
    assert out == [{"from": "1.1", "to": "2.4", "register": "mid", "level": 7}]


def test_phrase_gap_of_a_bar_splits():
    g = Grid([(0, 120.0)])
    levels = "8" * 16 + "0" * 16 + "4" * 16
    reg = "9" * 16 + "." * 16 + "1" * 16
    out = mm.phrases(levels, reg)
    assert out == [{"from": "1.1", "to": "1.4", "register": "high", "level": 8},
                   {"from": "3.1", "to": "3.4", "register": "low", "level": 4}]


def test_unpitched_voiced_steps_read_dot_and_keep_the_phrase_register():
    g = Grid([(0, 120.0)])
    ms = 4000
    x = glide(150, 300, ms)
    x[int(1000 * SR / 1000):int(1500 * SR / 1000)] = noise_burst(500, amp=0.5)  # steps 8-11
    reg = mm.register_digits(x, SR, mm.step_edges_ms(g, ms), "9" * 32)
    assert reg[8:12] == "...."
    assert "." not in reg[:7] and "." not in reg[13:]
    assert len(mm.phrases("9" * 32, reg)) == 1
    assert mm.phrases("9" * 4, "....") == [{"from": "1.1", "to": "1.1", "register": "mid", "level": 9}]


def test_phrase_gap_boundary():
    assert len(mm.phrases("7" * 4 + "0" * 3 + "7" * 4, "5" * 11)) == 1
    assert len(mm.phrases("7" * 4 + "0" * 4 + "7" * 4, "5" * 12)) == 2


def test_offgrid_onset_lands_on_the_nearest_step():
    g = Grid([(0, 120.0)])  # a step is 125 ms
    edges = mm.step_edges_ms(g, 2000)
    d, times = mm.onset_digits(clicks([125 + 40], 2000), SR, edges)
    assert d.index("9") == 1 and abs(times[0] - 165) <= 5
    d, _ = mm.onset_digits(clicks([125 + 80], 2000), SR, edges)
    assert d.index("9") == 2


# ---------------------------------------------------- sections, drops and build_map ----

BAR_MS = 2000  # 120 BPM


def kick_hit(sr, amp=0.5):
    """A 60 Hz thump with a decaying envelope: a sharp attack, as a kick has."""
    t = tone(60, 100, sr, amp)
    return t * np.exp(-np.arange(len(t)) / sr / 0.03).astype(np.float32)


def render(sr=SR, bars=24, kick=(), bass=(), bass_db=None, kick_db=None, perc=None, shift=0.0, first_ms=0,
           tail_ms=0):
    """Synthetic stems at 120 BPM: a kick on every beat of the `kick` bars, a bass tone in the
    `bass` bars (`bass_db[bar]` dB down), and 4-8 kHz percussion at `perc[bar]` amplitude."""
    total = first_ms + bars * BAR_MS + tail_ms
    drums, low = [], []
    for bar in kick:
        for beat in range(4):
            drums.append((first_ms + (bar - 1) * BAR_MS + beat * 500 + shift, kick_hit(sr, 0.5 * db(-(kick_db or {}).get(bar, 0)))))
    for bar, amp in (perc or {}).items():
        for beat in range(4):
            drums.append((first_ms + (bar - 1) * BAR_MS + beat * 500 + 250,
                          noise_burst(100, sr, amp, seed=bar * 4 + beat, low_hz=4000, high_hz=8000)))
    for bar in bass:
        gain = db(-(bass_db or {}).get(bar, 0))
        low.append((first_ms + (bar - 1) * BAR_MS, tone(80, BAR_MS, sr, 0.6 * gain)))
    z = silence(total, sr)
    return {"vocals": z, "drums": place(total, drums, sr), "bass": place(total, low, sr),
            "other": z.copy()}


def make(stems, sr=SR, anchors=((0, 120.0),), audio_ms=None, hot_cues=None,
         note="not in rekordbox"):
    audio_ms = audio_ms or len(stems["drums"]) * 1000 // sr
    return mm.build_map(track="Pedro Sampaio — Dançarina",
                        guid="0123ABCD-0123-4567-89AB-0123456789AB",
                        audio_sha="3f9c1a2b4d5e", audio_ms=audio_ms, anchors=list(anchors),
                        stems=stems, sr=sr, hot_cues=hot_cues,
                        hot_cues_note=None if hot_cues else note, separator="htdemucs")


def arrangement(sr=SR):
    full = list(range(5, 13)) + list(range(17, 25))
    perc = {b: 0.3 for b in (*range(5, 13), 17, 18)}
    perc.update({15: 0.1, 16: 0.2})
    return render(sr, kick=list(range(1, 13)) + list(range(17, 25)), bass=full, perc=perc)


def spans(m):
    return [(s["kind"], *s["bars"]) for s in m["sections"]]


def test_arrangement_sections_and_drops():
    m = make(arrangement())
    assert spans(m) == [("intro", 1, 4), ("drop", 5, 12), ("break", 13, 14), ("build", 15, 16),
                        ("drop", 17, 24)]
    assert [d["bar"] for d in m["drops"]] == [5, 17]
    assert all(d["db"] > 6 for d in m["drops"])


def test_one_bar_dip_is_not_a_break():
    allbars = list(range(1, 25))
    m = make(render(kick=[b for b in allbars if b != 9], bass=[b for b in allbars if b != 9]))
    assert spans(m) == [("groove", 1, 24)]
    assert m["drops"] == []


def test_filtered_bass_break():
    allbars = list(range(1, 25))
    down = {b: 12 for b in range(9, 13)}
    m = make(render(kick=allbars, bass=allbars, bass_db=down, kick_db=down))
    assert ("break", 9, 12) in spans(m)
    assert [d["bar"] for d in m["drops"]] == [13]


def test_bass_alone_filtered_with_full_kick_is_not_a_break():
    allbars = list(range(1, 25))
    loud_kick = {b: -18 for b in allbars}  # a kick that carries the low end, as in a club mix
    m = make(render(kick=allbars, bass=allbars, kick_db=loud_kick,
                    bass_db={b: 12 for b in range(9, 13)}))
    assert spans(m) == [("groove", 1, 24)]


def test_track_full_from_bar_one_starts_with_groove():
    allbars = list(range(1, 25))
    m = make(render(kick=allbars, bass=allbars))
    assert spans(m) == [("groove", 1, 24)]


def test_outro_after_last_full_bar():
    m = make(render(kick=range(1, 21), bass=range(1, 21)))
    assert spans(m) == [("groove", 1, 20), ("outro", 21, 24)]


def test_silences():
    db_ = np.array([-20.0] * 4 + [-120.0] * 2 + [-20.0] * 3 + [-70.0])
    assert mm.silences(db_) == [[5, 6], [10, 10]]
    assert mm.silences(np.full(4, -120.0)) == []


def test_grid_warning_when_kicks_are_off_grid():
    allbars = list(range(1, 25))
    off = make(render(kick=allbars, bass=allbars, shift=62.5))
    assert "grid_warning" in off and abs(off["grid"]["offset_ms"]) > 31
    on = make(render(kick=allbars, bass=allbars))
    assert "grid_warning" not in on and abs(on["grid"]["offset_ms"]) <= 5


def test_grid_offset_ms():
    g = Grid([(0, 120.0)])
    assert mm.grid_offset_ms([10.0, 510.0, 1020.0], g) == 10.0
    assert mm.grid_offset_ms([-20.0, 480.0, 1980.0], g) == -20.0
    assert mm.grid_offset_ms([], g) == 0.0


def test_build_map_passes_its_own_validation():
    allbars = list(range(1, 25))
    stems = render(kick=allbars, bass=allbars)
    for m in (make(stems, hot_cues={"A": "1.1", "B": "5.1"}), make(stems)):
        assert mm.problems_map(m) == []
        assert mm.problems_map(yaml.safe_load(mm.dump_map(m))) == []
    assert make(stems, hot_cues={"A": "1.1"})["hot_cues"] == {"A": "1.1"}
    assert make(stems)["hot_cues_note"] == "not in rekordbox"
    m = make(stems)
    assert m["grid"] == {"bpm": 120.0, "downbeat": "0:00.000", "anchors": [[0, 120.0]],
                         "offset_ms": m["grid"]["offset_ms"]}
    assert m["audio"] == {"sha256": "3f9c1a2b4d5e", "ms": 48000} and m["bars"] == 24


def test_same_bars_at_48k():
    a, b = make(arrangement(44100), 44100), make(arrangement(48000), 48000)
    assert ({v: a["voices"][v]["bars"] for v in mm.VOICES}
            == {v: b["voices"][v]["bars"] for v in mm.VOICES})
    assert a["sections"] == b["sections"]
    assert [d["bar"] for d in a["drops"]] == [d["bar"] for d in b["drops"]]
    assert all(abs(x["db"] - y["db"]) < 0.5 for x, y in zip(a["drops"], b["drops"]))


def test_pickup_before_first_anchor_and_partial_last_bar():
    first = 3998
    stems = render(bars=10, kick=range(1, 11), bass=range(1, 11), first_ms=first, tail_ms=1000)
    stems["other"] = place(len(stems["other"]) * 1000 / SR, [(0, tone(440, first, amp=0.5))])
    m = make(stems, anchors=[(first, 120.0)], audio_ms=first + int(10.5 * BAR_MS))
    assert m["bars"] == 11
    assert sum(len(s) for s in m["steps"]["kick"]) == 176
    assert m["voices"]["other"]["bars"] == "0" * 11
    assert m["grid"]["downbeat"] == "0:03.998"


def test_cue_text():
    g = Grid([(0, 120.0)])
    assert mm.cue_text(g.ms(57), g) == "57.1"
    assert mm.cue_text(g.ms(9) + 500, g) == "9.2"
    assert mm.cue_text(g.ms(9) + 100, g) == "9.1+100ms"
    assert mm.cue_text(g.ms(9) + 400, g) == "9.2-100ms"
    assert mm.cue_text(g.ms(9) + 20, g) == "9.1"


def test_is_stale():
    m = make(render(kick=[1], bass=[1], bars=2))
    same = dict(audio_sha="3f9c1a2b4d5e", guid="0123ABCD-0123-4567-89AB-0123456789AB",
                anchors=[(0, 120.0)])
    assert mm.is_stale(m, **same) is False
    assert mm.is_stale(m, **{**same, "audio_sha": "000000000000"}) is True
    assert mm.is_stale(m, **{**same, "guid": "0123ABCD-0123-4567-89AB-0123456789AC"}) is True
    assert mm.is_stale(m, **{**same, "anchors": [(0, 121.0)]}) is True
    assert mm.is_stale(m, **{**same, "anchors": [(0, 120.0), (4000, 120.0)]}) is True


def real_kick_stems(bpm=130.0, bars=4, shift=0.0):
    beat = 60000 / bpm
    total = bars * 4 * beat
    drums = place(total, [(i * beat + shift, real_kick(SR, 300)) for i in range(bars * 4)])
    z = silence(total)
    return {"vocals": z, "drums": drums, "bass": z.copy(), "other": z.copy()}, beat


def test_kick_onsets_sit_on_the_beat():
    stems, beat = real_kick_stems()
    g = Grid([(0, 130.0)])
    edges = mm.step_edges_ms(g, int(4 * 4 * beat))
    voices = mm.voices_from_stems(stems, SR)
    digits, times = mm.kick_onsets(stems["drums"], voices["kick"], SR, edges)
    assert digits == "9...9...9...9..." * 4
    assert len(times) == 16
    assert all(abs(t - i * beat) <= 10 for i, t in enumerate(times))


def test_no_grid_warning_for_a_real_kick_on_the_grid():
    stems, beat = real_kick_stems()
    m = make(stems, anchors=((0, 130.0),))
    assert "grid_warning" not in m and abs(m["grid"]["offset_ms"]) <= 10
    step = beat / 4
    shifted, _ = real_kick_stems(shift=step / 2)
    assert "grid_warning" in make(shifted, anchors=((0, 130.0),))


def test_one_bar_stab_inside_a_break_is_not_a_drop():
    full = [*range(1, 9), 13, *range(17, 25)]
    m = make(render(kick=full, bass=full))
    assert spans(m) == [("groove", 1, 8), ("break", 9, 16), ("drop", 17, 24)]
    assert [d["bar"] for d in m["drops"]] == [17]


def kick_string(events, total_ms, bpm=130.0):
    z = silence(total_ms)
    drums = place(total_ms, events)
    stems = {"vocals": z, "drums": drums, "bass": z.copy(), "other": z.copy()}
    voices = mm.voices_from_stems(stems, SR)
    edges = mm.step_edges_ms(Grid([(0, bpm)]), int(total_ms))
    return mm.kick_onsets(drums, voices["kick"], SR, edges)


def test_quiet_intro_kicks_are_kept():
    beat = 60000 / 130
    quiet = real_kick(SR, 300) * db(-20)
    events = [(i * beat, quiet if i < 16 else real_kick(SR, 300)) for i in range(32)]
    digits, times = kick_string(events, 32 * beat)
    assert [i for i, c in enumerate(digits[:16]) if c != "."] == [0, 4, 8, 12]


def test_two_kicks_90_ms_apart_are_both_kept():
    events = [(500, real_kick(SR, 300)), (590, real_kick(SR, 300)), (2000, real_kick(SR, 300))]
    _, times = kick_string(events, 3000)
    assert len(times) == 3 and times == sorted(set(times))
    assert all(abs(t - p) <= 10 for t, p in zip(times, (500, 590, 2000)))


def test_a_kick_at_the_file_start_is_kept():
    _, times = kick_string([(0, real_kick(SR, 300)), (500, real_kick(SR, 300))], 1500)
    assert len(times) == 2 and abs(times[0]) <= 10


def test_short_full_stretch_after_the_intro_is_a_drop():
    full = [*range(5, 6), *range(9, 25)]
    m = make(render(kick=full, bass=full))
    assert spans(m)[0] == ("intro", 1, 4) and spans(m)[1] == ("drop", 5, 5)
    assert [d["bar"] for d in m["drops"]][:2] == [5, 9]
