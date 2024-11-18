'''
Types describing the Git objects that live in the object database
of a git repository.

These types are mirrored b the `xontrib.xgit.entry_types` module, which
act as references to these objects in the tree, blob, and commit objects
found in tree objects. (tags are not stored in trees)

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from typing import (
    Protocol, runtime_checkable, Any, Iterator, Literal,
    Sequence, Mapping, TypeAlias,
)
from abc import abstractmethod
from io import IOBase

from xontrib.xgit.types import (
    CleanupAction, GitHash, GitObjectType,
)
import xontrib.xgit.person as xp

from xontrib.xgit.object_types_base import GitObject


EntryObject: TypeAlias = 'GitTree | GitBlob | GitCommit'
'''
A type alias for the types of objects that can be found in a git tree.
'''

@runtime_checkable
class GitTree(GitObject, Protocol):
    """
    A git tree object.
    """
    @property
    def type(self) -> Literal['tree']:
        return 'tree'

    @abstractmethod
    def items(self) -> Iterator[tuple[str, EntryObject]]: ...

    @abstractmethod
    def keys(self) -> Iterator[str]: ...

    @abstractmethod
    def values(self) -> Iterator[EntryObject]: ...

    @property
    @abstractmethod
    def hashes(self) -> Mapping[GitHash, 'et.GitEntry']: ...

    @abstractmethod
    def __getitem__(self, key: str) -> EntryObject: ...

    @abstractmethod
    def __iter__(self) -> Iterator[str]:  ...

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __contains__(self, key: str) -> bool: ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> EntryObject: ...

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
    def author(self) -> 'xp.CommittedBy': ...

    @property
    @abstractmethod
    def committer(self) -> 'xp.CommittedBy': ...
    @property
    @abstractmethod
    def tree(self) -> GitTree: ...

    @property
    @abstractmethod
    def parents(self) -> 'Sequence[GitCommit]': ...

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
    def tagger(self) -> 'xp.CommittedBy': ...

    @property
    @abstractmethod
    def message(self) -> str: ...

    @property
    @abstractmethod
    def tag_type(self) -> GitObjectType: ...

    @property
    @abstractmethod
    def signature(self) -> str: ...


import xontrib.xgit.entry_types as et
