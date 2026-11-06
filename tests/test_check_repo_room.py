"""The `lightshow-room` rule and the room as a show input."""
import check_repo
from show_language import ShowSource

RULE = "lightshow-room"
ROOM = "lightshows/room.yml"
RIG = """\
room: {shape: rectangle, front: N}
fixtures:
  mover-ne: {node: Mover 1, corner: NE, kind: mover}
  hue:      {kind: hue-chandelier, corner: centre, lamps: 7, follows: main-track}
matrix:
  rows: [colour, white]
  zone_order: row-major-top-left
  white_max: 0.6
"""
GOOD = """\
size: {x: 5.0, y: 4.0, z: 2.6}
assumed: true
fixtures:
  mover-ne: [5.0, 4.0, 2.3]
  hue: [2.5, 2.0, 2.2]
booth: [2.5, 4.0, 1.2]
aims:
  centro:
    figure: "no centro"
    preset: Dance Floor Centre
    status: configured
    targets: {mover-ne: [2.5, 2.0, 0.0]}
"""


def test_no_room_file_is_no_finding(mini_repo):
    assert mini_repo.findings() == []


def test_a_valid_room_passes(mini_repo):
    mini_repo.write("lightshows/rig.yml", RIG)
    mini_repo.write(ROOM, GOOD)
    assert mini_repo.findings() == []


def test_a_room_problem_is_a_finding_at_its_line(mini_repo):
    mini_repo.write("lightshows/rig.yml", RIG)
    mini_repo.write(ROOM, GOOD.replace("[2.5, 4.0, 1.2]", "[9.0, 4.0, 1.2]"))
    found = mini_repo.findings(RULE)
    assert [(p, r) for p, _, r in found] == [(ROOM, RULE)]
    assert found[0][1] > 0


def test_a_room_fixture_unknown_to_the_rig_is_a_finding(mini_repo):
    mini_repo.write("lightshows/rig.yml", RIG)
    mini_repo.write(ROOM, GOOD.replace("  hue:", "  ghost:"))
    assert len(mini_repo.findings(RULE)) == 2  # ghost unknown, hue without a place


def test_an_unparsable_room_reports_parse_error_only(mini_repo):
    mini_repo.write(ROOM, "a: [1, 2\n")
    assert [f[2] for f in mini_repo.findings()] == ["parse-error"]


def test_show_inputs_carry_the_room_only_when_valid(mini_repo):
    source = ShowSource("x", "lightshows/shows/x", {}, {})
    mini_repo.write("lightshows/rig.yml", RIG)
    mini_repo.write(ROOM, GOOD)
    repo = check_repo.load_repo(mini_repo.root)
    assert check_repo.show_inputs(repo, source).room.aims["centro"].preset == "Dance Floor Centre"
    mini_repo.write(ROOM, GOOD.replace("assumed: true", "assumed: 3"))
    repo = check_repo.load_repo(mini_repo.root)
    assert check_repo.show_inputs(repo, source).room is None
