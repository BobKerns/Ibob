"""
An reference to a `GitObject` in the repository.

This incudes `GitCommit`, `GitTree`, `GitTagObject` objects, as well as
refs and entries in trees.
"""

from typing import Optional
from pathlib import Path

from xontrib.xgit.xgit_types import (
    GitEntryMode,
    GitObject, GitTreeEntry,
)


class _GitTreeEntry(GitTreeEntry):
    """
    An entry in a git tree. In addition to referencing a `GitObject`,
    it supplies the mode and name.
    """

    _name: str
    _object: GitObject
    _mode: GitEntryMode
    _path: Path

    @property
    def type(self):
        return self._object.type

    @property
    def hash(self):
        return self._object.hash

    @property
    def mode(self):
        return self._mode

    @property
    def size(self):
        return self._object.size

    @property
    def name(self):
        return self._name

    @property
    def entry(self):
        return f"{self.mode} {self.type} {self.hash}\t{self.name}"

    @property
    def entry_long(self):
        size = self.size
        if isinstance(size, int):
            size = size if size >= 0 else '-'
        return f"{self.mode} {self.type} {self.hash} {size}\t{self.name}"

    @property
    def object(self):
        return self._object

    @property
    def path(self):
        return self._path

    def __init__(self, object: GitObject, name: str, mode: GitEntryMode, path: Optional[Path] = None):
        self._object = object
        self._name = name
        self._mode = mode
        self._path = path or Path(name)

    def __str__(self):
        return f"{self.entry_long} {self.name}"

    def __repr__(self):
        return f"GitTreeEntry({self.name!r}, {self.entry_long!r})"

    def __format__(self, fmt: str):
        return f"{self.entry_long.__format__(fmt)} {self.name}"

    def _repr_pretty_(self, p, cycle):
        return self._object._repr_pretty_(p, cycle)
