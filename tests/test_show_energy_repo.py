"""Calibration of the music energy on the committed Hï Ibiza show and its v2 maps (no audio):
the weights of `show_energy.MUSIC_WEIGHTS` are tuned until these two acceptance tests pass
(spec section A2); the thresholds are the spec's and never move."""
from collections import Counter
from statistics import mean

import pytest

import check_repo
import show_energy as se
import show_language
import show_views as sv
from conftest import REPO_ROOT

SHOW = REPO_ROOT / check_repo.SHOWS_DIR / "hi-ibiza-pulso"


@pytest.fixture(scope="module")
def night():
    errors: list = []
    repo = check_repo.load_repo(REPO_ROOT)
    source = check_repo.load_show_folder(REPO_ROOT, SHOW, errors)
    assert source is not None and not errors
    show, found = show_language.compile_show(source, check_repo.show_inputs(repo, source))
    assert show is not None, found
    clock = sv.build_clock(show)
    return show, clock, se.night_energy(show, clock)


def leg_values(te, clock, series):
    first, last = clock.tracks[te.index].leg
    return [te.at(series, b) for b in range(first, last + 1) if te.at(series, b) is not None]


def test_hi_ibiza_music_energy_does_not_saturate(night):
    _, clock, energies = night
    shares = Counter(d for t in energies for d in leg_values(t, clock, "music_night"))
    assert max(shares.values()) / sum(shares.values()) <= 0.40


def test_hi_ibiza_drops_after_a_break_rise_in_music_energy(night):
    show, clock, energies = night
    rising = []
    for track, te in zip(show.tracks, energies):
        sections = track.map["sections"]
        for i, section in enumerate(sections):
            if section["kind"] != "drop" or i == 0 or sections[i - 1]["kind"] not in ("break", "build"):
                continue
            d = section["bars"][0]
            before = [te.at("music", b) for b in range(d - 4, d)]
            after = [te.at("music", b) for b in range(d, d + 4)]
            if None in before or None in after:
                continue
            rising.append(mean(after) > mean(before))
    assert rising, "no drop follows a break or build"
    assert sum(rising) / len(rising) >= 0.80
