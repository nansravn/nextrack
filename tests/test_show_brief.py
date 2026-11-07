"""The set brief (show_brief.py) on the mini repo's set: two tracks, two maps, no show needed."""
from pathlib import Path

import musical_map
import show_analysis
import show_brief
import show_views
from check_repo import load_repo
from showdata import FILE_1, FILE_2, TRACK_2, put_show, show_map

SET = "sets/teste.md"


def brief(repo):
    return show_brief.render_brief(load_repo(repo.root), SET)


def part(text, header):
    """The lines under `header`, up to the next blank line."""
    lines = text.splitlines()
    out = []
    for line in lines[lines.index(header) + 1:]:
        if not line:
            break
        out.append(line)
    return out


def test_brief_lists_every_set_track_in_order(mini_repo):
    put_show(mini_repo)
    text = brief(mini_repo)
    assert [h for h in text.splitlines() if h and not h.startswith(" ")] == \
        ["night", "tracks", "drops", "target", "labels", "missing"]
    names = [line for line in part(text, "tracks") if line.startswith("  ") and line[2].isdigit()]
    assert len(names) == 2
    assert "1. Pedro Sampaio — Dançarina" in names[0] and "2. Chiclete com Banana — Voa Voa" in names[1]
    assert "enters 0:00" in text and "B 5 · G 25" in text and "mix 8 bars" in text


def test_brief_ranks_the_drops(mini_repo):
    put_show(mini_repo)
    rows = part(brief(mini_repo), "drops")
    assert len(rows) == 4
    salience = [float(r.rsplit("S ", 1)[1].split()[0]) for r in rows]
    assert salience == sorted(salience, reverse=True)
    assert rows[0].lstrip().startswith("1. ")


def test_map_drops_gives_every_sounding_drop_a_salience():
    maps = [show_map(), show_map(track="Chiclete com Banana — Voa Voa")]
    found = show_analysis.map_drops(maps, show_views.set_clock(maps, [None, None]))
    assert {(f["index"], f["d"]) for f in found} == {(0, 9), (0, 21), (1, 9), (1, 21)}
    assert all(0 <= f["salience"] <= 1 for f in found)


def test_brief_reports_a_missing_map_under_missing(mini_repo):
    put_show(mini_repo)
    mini_repo.path(f"lightshows/maps/{FILE_2}").unlink()
    text = brief(mini_repo)
    assert "Voa Voa: no map; the clock leaves it out" in "\n".join(part(text, "missing"))
    assert "no clock (no usable map)" in text


def test_brief_marks_a_v1_map_as_interim(mini_repo):
    put_show(mini_repo)
    data = show_map()
    data["map_version"] = 2
    data["mix"] = {"loudness": "5" * 32, "brightness": "5" * 32}
    mini_repo.write(f"lightshows/maps/{FILE_1}", musical_map.dump_map(data))
    text = brief(mini_repo)
    missing = "\n".join(part(text, "missing"))
    assert "Dançarina" not in missing and "Voa Voa: v1 map (no mix)" in missing
    assert text.count("(interim)") == 1


def test_brief_reports_an_invalid_map(mini_repo):
    put_show(mini_repo)
    mini_repo.write(f"lightshows/maps/{FILE_2}", musical_map.dump_map({**show_map(track=TRACK_2), "sections": "x"}))
    assert "invalid map" in "\n".join(part(brief(mini_repo), "missing"))


def test_brief_is_deterministic(mini_repo):
    put_show(mini_repo)
    assert brief(mini_repo) == brief(mini_repo)


def test_brief_target_is_one_character_per_minute():
    assert show_brief._target_strip([(0.0, 4), (120.0, 8)], 180.0) == "578"
    assert show_brief._target_strip([(0.0, 10)], 60.0) == "X"
    assert show_brief._target_strip([], 60.0) == ""


def strip_energy(repo):
    """The `target` strip of the brief."""
    return part(brief(repo), "target")[-1].strip()


def test_brief_target_runs_from_the_first_to_the_last_owner_energy(mini_repo):
    put_show(mini_repo)
    strip = strip_energy(mini_repo)
    assert strip and set(strip) <= set("78")


def test_brief_track_without_energy_takes_the_block_range(mini_repo):
    put_show(mini_repo)
    mini_repo.edit("blocks/alpha-festa.md", "Dançarina        · e8  abre", "Dançarina · 8A · 120")
    mini_repo.edit("blocks/alpha-festa.md", "Voa Voa    · e7", "Voa Voa · 8A · 120")
    mini_repo.edit("tracks/alpha.yml", "  energy: 8\n", "")
    mini_repo.edit("tracks/alpha.yml", "  energy: 7\n", "")
    text = brief(mini_repo)
    owners = [line.split("owner ")[1].split(" ·")[0] for line in text.splitlines() if "owner " in line]
    assert owners == ["e7", "e8"]
    assert set(strip_energy(mini_repo)) <= set("78")


def test_brief_labels_section_lists_the_questions(mini_repo):
    put_show(mini_repo)
    assert part(brief(mini_repo), "labels") == ["  none"]      # two tracks cannot differ by three places
    real = show_brief.render_brief(load_repo(Path(__file__).resolve().parents[1]), "sets/hi-ibiza-pulso.md")
    questions = part(real, "labels")
    assert questions and all("check the label" in q and "owner energy e" in q for q in questions)
