import numpy as np

import musical_map as mm
from soundswitch_format import Grid
from synth import SR, db, noise_burst, pan, place, silence, tone


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
