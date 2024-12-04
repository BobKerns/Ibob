'''
Abstract base class for all entry types.

See `entries.py` for the concrete implementations, which have the same
names as the abstract classes here, but prefixed with '_'

You should use these types rather than the concrete implementations.
Accessing the entries from a `GitTree` will return the concrete,
properly registered, and this should be the only way to get them.

These are `Protocol` classes, so they can be used as a type hint for
duck typing.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from abc import abstractmethod
from typing import (
    Protocol, Optional, TypeVar, Generic, TypeAlias, runtime_checkable,
    TYPE_CHECKING,
)
from pathlib import PurePosixPath

from xontrib.xgit.types import GitEntryMode, GitObjectType, ObjectId

if TYPE_CHECKING:
    import xontrib.xgit.object_types as ot
    import xontrib.xgit.context_types as ct

ParentObject: TypeAlias = 'ot.GitTree | ot.GitCommit | ot.GitTagObject'
EntryObject: TypeAlias = 'ot.GitTree | ot.GitBlob | ot.GitCommit'
OBJ = TypeVar('OBJ', bound='EntryObject', covariant=True)

@runtime_checkable
class GitEntry(Generic[OBJ], Protocol):
    """
    An entry in a git tree. In addition to referencing a `GitObject`,
    it supplies the mode and name.

    It makes the fields of the referenced`GetObject available as properties.
    """
    @property
    @abstractmethod
    def type(self) -> GitObjectType:
        ...
    @property
    @abstractmethod
    def hash(self) -> ObjectId: ...
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
    def object(self) -> OBJ: ...
    @property
    @abstractmethod
    def repository(self) -> 'ct.GitRepository': ...
    @property
    @abstractmethod
    def parent_object(self) -> 'Optional[ParentObject]': ...
    @property
    @abstractmethod
    def parent(self) -> Optional['GitEntryTree']: ...
    @property
    @abstractmethod
    def path(self) -> PurePosixPath: ...


@runtime_checkable
class GitEntryTree(GitEntry, Protocol):
    __path: Optional[PurePosixPath] = None
    @abstractmethod
    def __getitem__(self, key: str) -> 'GitEntry': ...

class GitEntryBlob(GitEntry):
    ...

class GitEntryCommit(GitEntry):
    ...


