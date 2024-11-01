'''
Auxiliary types for xgit xontrib. These are primarily used for internal purposes.

Types for public use will be defined in the xgit module via `__init__.py`. and the
`__all__` variable.
'''

from abc import abstractmethod
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
class GitRepository(Protocol):
    """
    A git repository.
    """

    repository: Path = Path(".git")
    """
    The path to the repository. If this is a worktree,
    it is the path to the worktree-specific part.
    For the main worktree, this is the same as `common`.
    """
    common: Path = Path(".git")
    """
    The path to the common part of the repository. This is the same for all worktrees.
    """


@runtime_checkable
class GitWorktree(GitRepository, Protocol):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """

    worktree: Path | None = Path(".")

@runtime_checkable
class GitContext(Protocol):
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
    ) -> "GitContext":
        ...


@runtime_checkable
class GitId(Protocol):
    """
    Anything that has a hash in a git repository.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    @abstractmethod
    def hash(self) -> GitHash:
        ...

@runtime_checkable
class GitObject(GitId, Protocol):
    """
    A git object.
    """
    @abstractmethod
    def __init__(self, hash: GitHash, size: int,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    @abstractmethod
    def type(self) -> GitObjectType:
        ...
    @property
    @abstractmethod
    def size(self) -> int:
        ...


@runtime_checkable
class GitTree(GitObject, Protocol):
    """
    A git tree object.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    def type(self) -> Literal['tree']:
        return 'tree'

    @property
    @abstractmethod
    def entries(self) -> dict[str, GitObject]:
        ...

@runtime_checkable
class GitBlob(GitObject, Protocol):
    """
    A git blob object.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    def type(self) -> Literal['blob']:
        return 'blob'
    @property
    @abstractmethod
    def data(self) -> bytes:
        ...
    @property
    @abstractmethod
    def lines(self) -> Iterator[str]:
        ...
    @property
    @abstractmethod
    def stream(self) -> IOBase:
        ...


@runtime_checkable
class GitCommit(GitObject, Protocol):
    """
    A git commit object.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    def type(self) -> Literal['commit']:
        return 'commit'
    @property
    @abstractmethod
    def message(self) -> str:
        ...
    @property
    @abstractmethod
    def author(self) -> str:
        ...
    @property
    @abstractmethod
    def committer(self) -> str:
        ...
    @property
    @abstractmethod
    def author_date(self) -> datetime:
        ...
    @abstractmethod
    def committer_date(self) -> datetime:
        ...
    @property
    @abstractmethod
    def tree(self) -> GitTree:
        ...
    @property
    @abstractmethod
    def parents(self) -> 'Sequence[GitCommit]':
        ...


@runtime_checkable
class GitTagObject(GitObject, Protocol):
    """
    A git tag object.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 loader: Optional[GitLoader] = None,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    def type(self) -> Literal['tag']:
        return 'tag'
    @property
    @abstractmethod
    def object(self) -> GitObject:
        ...
    @property
    @abstractmethod
    def tagger(self) -> str:
        ...
    @property
    @abstractmethod
    def created(self) -> datetime:
        ...
    @property
    @abstractmethod
    def message(self) -> str:
        ...


class GitTreeEntry(GitObject, Protocol):
    """
    An entry in a git tree. In addition to referencing a `GitObject`,
    it supplies the mode and name.

    It makes the fields of `GetObject available as properties.
    """
    @property
    @abstractmethod
    def type(self) -> GitObjectType:
        ...
    @property
    @abstractmethod
    def hash(self) -> GitHash:
        ...
    @property
    @abstractmethod
    def mode(self) -> GitEntryMode:
        ...
    @property
    @abstractmethod
    def size(self) -> int:
        ...
    @property
    @abstractmethod
    def name(self) -> str:
        ...
    @property
    @abstractmethod
    def entry(self) -> str:
        ...
    @property
    @abstractmethod
    def entry_long(self) -> str:
        ...
    @property
    @abstractmethod
    def object(self) -> GitObject:
        ...
    @property
    @abstractmethod
    def path(self) -> Path:
        ...
