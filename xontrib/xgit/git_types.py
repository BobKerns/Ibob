'''
Types describing git objects and related types.
'''

from pathlib import Path
from typing import (
    Protocol, runtime_checkable, Optional, Any, Iterator, Literal, Sequence,
)
from abc import abstractmethod
from io import IOBase
from datetime import datetime


from xontrib.xgit.types import (
    CleanupAction, GitHash, GitEntryMode, GitObjectType,
)


@runtime_checkable
class GitId(Protocol):
    """
    Anything that has a hash in a git repository.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
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
    @property
    def type(self) -> Literal['tree']:
        return 'tree'

    @abstractmethod
    def items(self) -> dict[str, GitObject]: ...

    @abstractmethod
    def keys(self) -> Iterator[str]: ...

    @abstractmethod
    def values(self) -> Iterator[GitObject]: ...

    @abstractmethod
    def __getitem__(self, key: str) -> GitObject: ...

    @abstractmethod
    def __iter__(self) -> Iterator[str]:  ...

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __contains__(self, key: str) -> bool: ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> GitObject: ...

    @abstractmethod
    def __eq__(self, other: Any) -> bool: ...

    def __bool__(self) -> bool: ...


@runtime_checkable
class GitBlob(GitObject, Protocol):
    """
    A git blob object.
    """
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
    @property
    def type(self) -> Literal['commit']:
        return 'commit'

    @property
    @abstractmethod
    def message(self) -> str: ...

    @property
    @abstractmethod
    def author(self) -> str: ...

    @property
    @abstractmethod
    def author_date(self) -> datetime:  ...

    @property
    @abstractmethod
    def author_email(self) -> str:  ...

    @property
    @abstractmethod
    def author_name(self) -> str: ...

    @property
    @abstractmethod
    def committer(self) -> str: ...
    @property
    @abstractmethod
    def committer_date(self) -> datetime: ...

    @property
    @abstractmethod
    def committer_email(self) -> datetime: ...

    @property
    @abstractmethod
    def committer_name(self) -> datetime: ...

    @property
    @abstractmethod
    def tree(self) -> GitTree: ...

    @property
    @abstractmethod
    def parents(self) -> 'Sequence[GitCommit]':
        ...

    @property
    @abstractmethod
    def signature(self) -> str: ...

@runtime_checkable
class GitTagObject(GitObject, Protocol):
    """
    A git tag object.
    """
    @property
    def type(self) -> Literal['tag']:
        return 'tag'

    @property
    @abstractmethod
    def object(self) -> GitObject:  ...

    @property
    @abstractmethod
    def tagger(self) -> str: ...

    @property
    @abstractmethod
    def tagger_name(self) -> str: ...

    @property
    @abstractmethod
    def tagger_email(self) -> str: ...

    @property
    @abstractmethod
    def created(self) -> datetime: ...

    @property
    @abstractmethod
    def message(self) -> str: ...

    @property
    @abstractmethod
    def tag_type(self) -> GitObjectType: ...

    @property
    @abstractmethod
    def signature(self) -> str: ...


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
    def hash(self) -> GitHash: ...
    @property
    @abstractmethod
    def mode(self) -> GitEntryMode: ...
    @property
    @abstractmethod
    def size(self) -> int: ...
    @property
    @abstractmethod
    def name(self) -> str: ...
    @property
    @abstractmethod
    def entry(self) -> str: ...
    @property
    @abstractmethod
    def entry_long(self) -> str: ...
    @property
    @abstractmethod
    def object(self) -> GitObject: ...
    @property
    @abstractmethod
    def parent_object(self) -> Optional[GitObject]: ...
    @property
    @abstractmethod
    def parent(self) -> Optional['GitTreeEntry']: ...
    @property
    @abstractmethod
    def path(self) -> Path: ...
    @abstractmethod
    def __getitem__(self, key: str) -> 'GitTreeEntry': ...

@runtime_checkable
class GitRef(Protocol):
    """
    Any ref, usually a branch or tag, usually pointing to a commit.
    """
    @property
    def name(self) -> str: ...
    @property
    def target(self) -> GitObject: ...

class Branch(GitRef, Protocol):
    """
    A branch ref.
    """
    def branch_name(self) -> str: ...


class RemoteBranch(GitRef, Protocol):
    """
    A branch ref.
    """
    def remote_branch_name(self) -> str: ...

class Tag(GitRef, Protocol):
    """
    A tag ref.
    """
    def tag_name(self) -> str: ...