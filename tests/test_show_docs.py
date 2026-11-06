"""The show language manual names every gesture and every rule the code registers."""
from pathlib import Path

from show_gestures import GESTURES
from show_rules import RULES

ROOT = Path(__file__).resolve().parent.parent


def test_the_show_readme_names_every_gesture_and_rule():
    text = (ROOT / "lightshows/shows/README.md").read_text(encoding="utf-8")
    missing = [n for n in [*GESTURES, *RULES] if f"`{n}`" not in text]
    assert not missing
