'''
Auxiliary types for xgit xontrib. These are primarily used for internal purposes.

Types for public use will be defined in the xgit module via `__init__.py`. and the
`__all__` variable.
'''

from datetime import datetime
from io import IOBase
from typing import (
    Callable, Iterator, TypeAlias, Literal, Protocol, runtime_checkable,
    Sequence
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


GitObjectReference: TypeAlias = tuple[ContextKey, str | None]
"""
A reference to a git object in a tree in a repository.
"""

from typing import Optional
from pathlib import Path

@runtime_checkable
class GitContext_(Protocol):
    """
    A git context. A protocol to avoid circular imports.
    """
    
    git_path: Path = Path(".")
    branch: str = ""
    commit: str = ""
    cwd: Path = Path(".")
    
    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        ...
        
    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        common: Optional[Path] = None,
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "GitContext_":
        ...


@runtime_checkable
class GitId_(Protocol):
    """
    Anything that has a hash in a git repository.
    """
    
    hash: GitHash
    
@runtime_checkable
class GitObject_(GitId_, Protocol):
    """
    A git object.
    """
    type: GitObjectType
    size: int


@runtime_checkable
class GitTree_(GitObject_, Protocol):
    """
    A git tree object.
    """
    
    entries: dict[str, GitObject_]


@runtime_checkable
class GitBlob_(GitObject_, Protocol):
    """
    A git blob object.
    """
    
    data: bytes
    lines: Iterator[str]
    stream: IOBase


@runtime_checkable
class GitCommit_(GitObject_, Protocol):
    """
    A git commit object.
    """
    
    tree: GitTree_
    parents: 'Sequence[GitCommit_]'


@runtime_checkable
class GitTagObject_( GitObject_, Protocol):
    """
    A git tag object.
    """
    
    object: GitObject_
    name: str
    tagger: str
    created: datetime
    message: str