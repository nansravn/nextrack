from soundswitch_format import FULL, Key

import lightshow as ls

BEAT = 500.0  # 120 bpm


def lit(frames):
    return [cells for _, cells in frames]


def rows_of(cells):
    return {r for r, _ in cells}


def cols_of(cells):
    return {c for _, c in cells}


def frames(draw, steps=4, unit=0, mirror=False, with_white=False):
    return ls.matrix_frames(draw, 0, int(steps * 100), 100, unit, mirror, with_white=with_white)


def test_rate_ms():
    assert ls.rate_ms("1/16", BEAT) == 125
    assert ls.rate_ms("1/8", BEAT) == 250
    assert ls.rate_ms("1/4", BEAT) == 500
    assert ls.rate_ms("1/2", BEAT) == 1000
    assert ls.rate_ms("2bar", BEAT) == 4000


def test_frame_times():
    fr = ls.matrix_frames("solid", 1000, 1400, 100, 0, False)
    assert [t for t, _ in fr] == [1000, 1100, 1200, 1300]


def test_fill_up_accumulates_from_bottom_and_holds():
    fr = frames("fill-up", 8)
    assert rows_of(fr[0][1]) == {6}
    assert rows_of(fr[1][1]) == {6, 5}
    assert rows_of(fr[2][1]) == {6, 5, 4}
    assert rows_of(fr[3][1]) == {6, 5, 4, 2}
    assert rows_of(fr[5][1]) == {0, 1, 2, 4, 5, 6}
    assert rows_of(fr[7][1]) == {0, 1, 2, 4, 5, 6}


def test_white_row_only_with_white():
    assert 3 not in rows_of(frames("solid")[0][1])
    assert 3 in rows_of(frames("solid", with_white=True)[0][1])
    fr = frames("rows-down", 7, with_white=True)
    assert [rows_of(c) for c in lit(fr)] == [{0}, {1}, {2}, {3}, {4}, {5}, {6}]


def test_columns_and_mirror():
    assert cols_of(frames("columns")[0][1]) == {0}
    assert cols_of(frames("columns", 3, unit=1, mirror=True)[0][1]) == {7}
    assert cols_of(frames("columns", 3, unit=1, mirror=True)[1][1]) == {6}
    assert cols_of(frames("columns", unit=1, mirror=False)[0][1]) == {0}
    assert cols_of(frames("columns", unit=0, mirror=True)[0][1]) == {0}
    assert cols_of(frames("columns", 9)[8][1]) == {0}


def test_rows_down_up():
    assert [rows_of(c) for c in lit(frames("rows-down", 7))] == [{0}, {1}, {2}, {4}, {5}, {6}, {0}]
    assert [rows_of(c) for c in lit(frames("rows-up", 3))] == [{6}, {5}, {4}]


def test_centre_out():
    fr = frames("centre-out", 5)
    assert cols_of(fr[0][1]) == {3, 4}
    assert cols_of(fr[1][1]) == {2, 5}
    assert cols_of(fr[3][1]) == {0, 7}
    assert cols_of(fr[4][1]) == {3, 4}


def test_zigzag_snake_skips_white_and_wraps():
    fr = frames("zigzag", 49)
    assert fr[0][1] == {(0, 0)}
    assert fr[7][1] == {(0, 7)}
    assert fr[8][1] == {(1, 7)}
    assert fr[16][1] == {(2, 0)}
    assert fr[24][1] == {(4, 7)}  # row 3 skipped
    assert fr[47][1] == {(6, 0)}  # last colour row runs right to left
    assert fr[48][1] == {(0, 0)}
    assert all(len(c) == 1 for c in lit(fr))
    ww = frames("zigzag", 25, with_white=True)
    assert ww[24][1] == {(3, 7)}  # fourth row of the snake runs right to left


def test_arrow_up_chevron_rises_and_wraps():
    fr = frames("arrow-up", 7)
    assert fr[0][1] == {(6, 3), (6, 4)}
    assert fr[1][1] == {(5, 3), (5, 4), (6, 2), (6, 5)}
    assert fr[3][1] == {
        (2, 3), (2, 4), (4, 2), (4, 5), (5, 1), (5, 6), (6, 0), (6, 7),
    }  # fmt: skip
    assert fr[5][1] == {(0, 3), (0, 4), (1, 2), (1, 5), (2, 1), (2, 6), (4, 0), (4, 7)}
    assert fr[6][1] == fr[0][1]


def test_solid():
    assert len(frames("solid")[0][1]) == 6 * 8


def test_cell_node():
    assert ls.cell_node({}, 0, 0) == 1
    assert ls.cell_node({}, 2, 7) == 24
    assert ls.cell_node({}, 3, 0) == 1
    assert ls.cell_node({}, 3, 7) == 8
    assert ls.cell_node({}, 4, 0) == 25
    assert ls.cell_node({}, 6, 7) == 48


def test_pulse_keys():
    assert ls.pulse_keys([1000], 300) == [Key(1000, FULL), Key(1299, 0)]
    assert ls.pulse_keys([0], 100, level=int(0.85 * 2**32)) == [
        Key(0, int(0.85 * 2**32)),
        Key(99, 0),
    ]


def test_pulse_keys_do_not_overlap():
    keys = ls.pulse_keys([1000, 1100, 1500], 300)
    assert keys == [
        Key(1000, FULL), Key(1099, 0),
        Key(1100, FULL), Key(1399, 0),
        Key(1500, FULL), Key(1799, 0),
    ]  # fmt: skip
    times = [k.t for k in keys]
    assert times == sorted(set(times))


def test_mover_hold_and_sweep_use_level():
    lvl = int(0.85 * 2**32)
    assert ls.mover_keys({"move": "hold"}, 0, 2000, BEAT, 0) == [Key(0, lvl), Key(2000, lvl)]
    assert ls.mover_keys({"move": "sweep"}, 0, 2000, BEAT, 0) == [Key(0, lvl), Key(2000, lvl)]
    half = int(0.5 * 2**32)
    assert ls.mover_keys({"move": "hold", "level": 0.5}, 0, 2000, BEAT, 0)[0] == Key(0, half)


def test_mover_pingpong_square_wave():
    move = {"move": "pingpong", "every": "1/4"}  # step 500
    a = ls.mover_keys(move, 0, 2000, BEAT, 0)
    b = ls.mover_keys(move, 0, 2000, BEAT, 1)
    assert a == [
        Key(0, FULL), Key(499, FULL), Key(500, 0),
        Key(1000, FULL), Key(1499, FULL), Key(1500, 0),
        Key(2000, 0),
    ]  # fmt: skip
    assert b == [
        Key(0, 0), Key(500, FULL), Key(999, FULL), Key(1000, 0),
        Key(1500, FULL), Key(1999, FULL), Key(2000, 0),
    ]  # fmt: skip
    for keys in (a, b):
        times = [k.t for k in keys]
        assert times == sorted(set(times))


def test_mover_pingpong_faster():
    move = {"move": "pingpong", "every": "1/2", "faster_from": 2, "faster_every": "1/4"}
    keys = ls.mover_keys(move, 0, 8000, BEAT, 0)  # bar = 2000 ms
    assert keys[0] == Key(0, FULL)
    assert keys[1] == Key(999, FULL)  # slow step 1000 in bar 1
    assert Key(2000, FULL) in keys and Key(2499, FULL) in keys  # fast step 500 after


def test_mover_blink():
    keys = ls.mover_keys({"move": "blink", "every": "1/2"}, 0, 2000, BEAT, 0)
    assert keys == [Key(0, FULL), Key(999, 0), Key(1000, FULL), Key(1999, 0)]


def test_mover_faster_from_is_an_absolute_bar():
    move = {"move": "pingpong", "every": "1/2", "faster_from": 27, "faster_every": "1/4"}
    bar = int(4 * BEAT)
    keys = ls.mover_keys(move, 0, 8 * bar, BEAT, 0, first_bar=21)
    lit_starts = [k.t for i, k in enumerate(keys) if k.level == FULL and keys[i + 1].t == k.t + (
        999 if k.t % 1000 == 0 and k.t < 6 * bar else 499)]
    assert 4000 in lit_starts  # bar 21 + 2 bars: still 1000 ms steps
    assert Key(4999, FULL) in keys
    assert Key(6 * bar, FULL) in keys and Key(6 * bar + 499, FULL) in keys  # 500 ms from bar 27
    assert Key(6 * bar + 999, FULL) not in keys


def test_mover_faster_from_at_or_before_first_bar_is_fast_from_start():
    move = {"move": "pingpong", "every": "1/2", "faster_from": 21, "faster_every": "1/4"}
    keys = ls.mover_keys(move, 0, 2000, BEAT, 0, first_bar=21)
    assert keys[:3] == [Key(0, FULL), Key(499, FULL), Key(500, 0)]


def test_pulse_keys_clipped_to_end():
    keys = ls.pulse_keys([0, 400], 1000, end=700)
    assert keys == [Key(0, FULL), Key(399, 0), Key(400, FULL), Key(700, 0)]
    assert ls.pulse_keys([0, 800], 100, end=700) == [Key(0, FULL), Key(99, 0)]


def test_blink_and_hue_pulse_stay_inside_span():
    bar = int(4 * BEAT)
    keys = ls.mover_keys({"move": "blink", "every": "2bar"}, 0, bar, BEAT, 0)
    assert keys == [Key(0, FULL), Key(bar, 0)]
    hue = ls.hue_keys("pulse", 0, 700, BEAT)
    times = [k.t for k in hue]
    assert max(times) <= 700 and times == sorted(set(times))


def test_hue_keys():
    lvl = int(0.85 * 2**32)
    assert ls.hue_keys("dark", 0, 2000, BEAT) == [Key(0, 0), Key(2000, 0)]
    assert ls.hue_keys("bright", 0, 2000, BEAT) == [Key(0, lvl), Key(2000, lvl)]
    assert ls.hue_keys("pulse", 0, 1000, BEAT) == [
        Key(0, FULL), Key(499, 0), Key(500, FULL), Key(999, 0),
    ]  # fmt: skip
