"""Reads playlists, tracks and hot cues from rekordbox's database, always through a copy.

pyrekordbox lives in the `analysis` dependency group, so it is imported only inside
`_open`. The pure helpers (`cues_from_rows`, `pick_playlist`) need nothing.
"""
from __future__ import annotations

import contextlib
import importlib.util
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Protocol

from musical_map import fold_name

ANALYSIS_HINT = "the analysis tools are not installed: run uv sync --group analysis"

# rekordbox cue `Kind`: 0 is a memory cue; 1..9 (4 is the loop slot) map to hot cues A..H.
KIND_TO_CUE = {1: "A", 2: "B", 3: "C", 5: "D", 6: "E", 7: "F", 8: "G", 9: "H"}


@dataclass
class RbTrack:
    title: str
    artist: str
    path: str
    bpm: float | None
    key: str | None
    cues: dict[str, int]  # letter -> ms


class RekordboxReader(Protocol):
    def playlist(self, name: str) -> list[RbTrack]: ...

    def track_for_file(self, file_name: str) -> RbTrack | None: ...


def cues_from_rows(rows: Iterable[tuple[int, int]]) -> dict[str, int]:
    """`(kind, ms)` rows to `{letter: ms}`; memory cues and unknown kinds are dropped, the first
    row of a letter wins."""
    cues: dict[str, int] = {}
    for kind, ms in rows:
        letter = KIND_TO_CUE.get(kind)
        if letter and letter not in cues:
            cues[letter] = ms
    return cues


def pick_playlist(names: list[str], want: str) -> str:
    """The exact name, else the only name containing `want` (case-insensitive)."""
    if names.count(want) == 1:
        return want
    if names.count(want) > 1:
        raise LookupError(f"{names.count(want)} playlists are named {want!r}: " + ", ".join(names))
    hits = [n for n in names if want.casefold() in n.casefold()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"no playlist matches {want!r}; playlists: " + ", ".join(names))
    raise LookupError(f"{len(hits)} playlists match {want!r}: " + ", ".join(hits))


def _base_name(path: str) -> str:
    parts = [p for p in re.split(r"[\\/]", path) if p]
    return parts[-1] if parts else ""


def pick_playlist_row(rows: list, want: str):
    """The playlist row for `want`: folders (`Attribute == 1` without songs) are skipped, and
    a name shared by two playlists is a `LookupError`."""
    lists = [r for r in rows if not (getattr(r, "Attribute", 0) == 1 and not r.Songs)]
    names = [r.Name for r in lists]
    return lists[names.index(pick_playlist(names, want))]


def pick_content_row(rows: Iterable, file_name: str):
    """The only content row whose path ends in `file_name`, or None; several are a `LookupError`."""
    want = fold_name(file_name)
    hits = [c for c in rows if fold_name(_base_name(c.FolderPath or "")) == want]
    if len(hits) > 1:
        raise LookupError(f"{len(hits)} tracks named {file_name!r}: " + ", ".join(c.FolderPath for c in hits))
    return hits[0] if hits else None


class _PyrekordboxReader:
    def __init__(self, db) -> None:
        self._db = db

    def _track(self, c) -> RbTrack:
        rows = [(cue.Kind, cue.InMsec) for cue in (c.Cues or [])]
        return RbTrack(
            title=c.Title or "",
            artist=c.Artist.Name if c.Artist is not None else "",
            path=c.FolderPath or "",
            bpm=c.BPM / 100 if c.BPM else None,
            key=c.Key.ScaleName if c.Key is not None else None,
            cues=cues_from_rows(rows),
        )

    def playlist(self, name: str) -> list[RbTrack]:
        chosen = pick_playlist_row(list(self._db.get_playlist().all()), name)
        songs = sorted(chosen.Songs, key=lambda s: s.TrackNo)
        return [self._track(s.Content) for s in songs]

    def track_for_file(self, file_name: str) -> RbTrack | None:
        row = pick_content_row(self._db.get_content().all(), file_name)
        return None if row is None else self._track(row)


@contextlib.contextmanager
def _open(folder: Path) -> Iterator[RekordboxReader]:
    if not (Path(folder) / "master.db").exists():
        raise LookupError(f"no master.db in {folder}")
    if importlib.util.find_spec("pyrekordbox.masterdb") is not None:
        from pyrekordbox.masterdb import MasterDatabase as Database
    else:
        from pyrekordbox import Rekordbox6Database as Database
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("master.db", "master.db-wal", "master.db-shm"):
            src = Path(folder) / name
            if src.exists():
                shutil.copy2(src, Path(tmp) / name)
        db = Database(path=Path(tmp) / "master.db", db_dir=tmp, unlock=True)
        try:
            yield _PyrekordboxReader(db)
        finally:
            db.close()


def open_rekordbox(folder: Path) -> contextlib.AbstractContextManager[RekordboxReader]:
    """Open a copy of the rekordbox database in `folder`; the copy is removed on exit."""
    if importlib.util.find_spec("pyrekordbox") is None:
        raise SystemExit(ANALYSIS_HINT)
    return _open(Path(folder))
