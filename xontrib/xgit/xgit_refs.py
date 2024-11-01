"""
An reference to a `GitObject` in the repository.

This incudes `GitCommit`, `GitTree`, `GitTagObject` objects, as well as
refs and entries in trees.
"""

from typing import Optional

from xontrib.xgit.xgit_types import (
    GitHash, GitLoader, GitEntryMode,
    GitObject_, GitObjectType,
)


class GitTreeEntry:
    """
    An entry in a git tree. In addition to referencing a `GitObject`,
    it supplies the mode and  
    """

    name: str

    object: GitObject_
    _mode: GitEntryMode

    @property
    def git_type(self):
        return self.object.type

    @property
    def hash(self):
        return self.object.hash

    @property
    def mode(self):
        return self._mode

    @property
    def entry(self):
        return f"{self.mode} {self.object.type} {self.hash}\t{self.name}"

    def __init__(self, name: str, object: GitObject_):
        self.name = name
        self.object = object

    def __str__(self):
        return f"{self.entry} {self.name}"

    def __repr__(self):
        return f"GitTreeEntry({self.name!r}, {self.entry!r})"

    def __format__(self, fmt: str):
        return f"{self.entry.__format__(fmt)} {self.name}"
