from mapdata import good_map

import musical_map as mm


def _put(repo, data, name=None):
    rel = f"lightshows/maps/{name or mm.slug(data['track'])}.yml"
    repo.write(rel, mm.dump_map(data))
    return rel


def test_musical_map_rule_passes_a_good_map(mini_repo):
    _put(mini_repo, good_map())
    assert mini_repo.findings() == []


def test_musical_map_rule_fails_for_a_track_outside_the_pool(mini_repo):
    rel = _put(mini_repo, good_map(track="Nobody — Nothing"))
    assert mini_repo.findings() == [(rel, 0, "musical-map")]


def test_musical_map_rule_fails_for_a_wrong_file_name(mini_repo):
    rel = _put(mini_repo, good_map(), name="dancarina")
    assert mini_repo.findings() == [(rel, 0, "musical-map")]


def test_musical_map_rule_reports_a_schema_problem_once(mini_repo):
    rel = _put(mini_repo, good_map(map_version=2))
    assert mini_repo.findings() == [(rel, 0, "musical-map")]


def test_an_unparsable_map_reports_parse_error_only(mini_repo):
    mini_repo.write("lightshows/maps/broken.yml", "a: [1, 2\n")
    assert [f[2] for f in mini_repo.findings()] == ["parse-error"]


def test_a_readme_in_the_maps_folder_is_not_a_map(mini_repo):
    mini_repo.write("lightshows/maps/README.md", "# Maps\n")
    assert mini_repo.findings() == []
