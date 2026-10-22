from pathlib import Path

import check_repo

SCRIPTS_README = Path(__file__).resolve().parent.parent / "scripts" / "README.md"


def test_dependencies_and_scripts_import():
    import mutagen, yaml, nextrack_tags
    assert mutagen.version >= (1, 47)
    assert tuple(int(p) for p in yaml.__version__.split(".")[:2]) >= (6, 0)
    assert callable(nextrack_tags.main)


def test_scripts_readme_lists_every_rule():
    """scripts/README.md documents every rule id, so the list cannot drift from the code."""
    text = SCRIPTS_README.read_text(encoding="utf-8")
    rule_ids = [fn.rule_id for fn in check_repo.RULES] + ["parse-error"]
    missing = [rule_id for rule_id in rule_ids if f"`{rule_id}`" not in text]
    assert not missing, f"scripts/README.md does not list: {', '.join(missing)}"
