'''
Auxiliary types for xgit xontrib. These are primarily used for internal purposes.

Types for public use will be defined in the xgit module via `__init__.py`. and the
`__all__` variable.
'''

from typing import (
    Callable, Generic, Protocol, TypeAlias, Literal, TypeVar,
)
from pathlib import Path

CleanupAction: TypeAlias = Callable[[], None]
"""
An action to be taken when the xontrib is unloaded.
"""

GitHash: TypeAlias = str
"""
A git hash. Defined as a string to make the code more self-documenting.
"""

ContextKey: TypeAlias = tuple[Path, Path, GitHash, GitHash]
"""
A key for uniquely identifying a `GitContext`
"""

GitLoader: TypeAlias = Callable[[], None]
"""
A function that loads the contents of a git object.
Use InitFn for loading a single attribute. This is for the case
where the entire object is loaded.
"""

GitEntryMode: TypeAlias = Literal[
    "040000",  # directory
    "100755",  # executable
    "100644",  # normal file
    "160000",  # submodule
    "20000",  # symlink
]
"""
The valid modes for a git tree entry.
"""

GitObjectType: TypeAlias = Literal["blob", "tree", "commit", "tag"]
"""
Valid types for a git object.
"""

GitEntryKey: TypeAlias = tuple[Path, str, str, str|None]

GitObjectReference: TypeAlias = tuple[ContextKey, str | None]
"""
A reference to a git object in a tree in a repository.
"""

class _NoValue:
    """A type for a marker for a value that is not passed in."""
    __match_args__ = ()
    def __repr__(self):
        return '_NO_VALUE'


_NO_VALUE = _NoValue()
"""A marker value to indicate that a value was not supplied"""

S = TypeVar('S', contravariant=True)
V = TypeVar('V', covariant=True)


class InitFn(Generic[S, V], Protocol):
    """
    A function that initializes a value from a source.
    """
    def __call__(self, source: S, /) -> V: ...