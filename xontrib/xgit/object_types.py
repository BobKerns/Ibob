'''
Types describing the Git objects that live in the object database
of a git repository.

These types are mirrored b the `xontrib.xgit.entry_types` module, which
act as references to these objects in the tree, blob, and commit objects
found in tree objects. (tags are not stored in trees)

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from abc import abstractmethod
from pathlib import PurePosixPath
from typing import (
    Optional, Protocol, overload, runtime_checkable, Any, Literal,
    TypeAlias, IO,
)
from collections.abc import Iterator, Sequence, Mapping\

from xontrib.xgit.types import (
    ObjectId, GitObjectType, GitEntryMode,
    CommitId, TreeId, TagId, BlobId,
)
from xontrib.xgit.identity_set import IdentitySet
import xontrib.xgit.person as xp
import xontrib.xgit.object_types as ot
import xontrib.xgit.context_types as ct
import xontrib.xgit.ref_types as rt
import xontrib.xgit.entry_types as et


EntryObject: TypeAlias = 'GitTree | GitBlob | GitCommit'
'''
A type alias for the types of objects that can be found in a git tree.
'''

Commitish: TypeAlias = 'CommitId|ot.GitCommit|ot.GitTagObject|rt.GitRef'
'''
A type alias for the types of objects that can be used to identify a commit.
'''
Treeish: TypeAlias = 'TreeId|ot.GitCommit|ot.GitTree|ot.GitTagObject|rt.GitRef'
'''
A type alias for the types of objects that can be used to identify a tree.
'''
Tagish: TypeAlias = 'TagId|ot.GitTagObject|rt.GitRef'
'''
A type alias for the types of objects that can be used to identify a tag.
'''
Blobish: TypeAlias = 'BlobId|ot.GitBlob|rt.GitRef'
'''
A type alias for the types of objects that can be used to identify a blob.
'''
Objectish: TypeAlias = 'ObjectId|ot.GitObject|rt.GitRef'
'''
A type alias for the types of objects that can be used to identify any object.
'''


@runtime_checkable
class GitId(Protocol):
    """
    Anything that has a hash in a git repository.
    """
    @abstractmethod
    def __init__(self, hash: ObjectId):
        ...
    @property
    @abstractmethod
    def hash(self) -> ObjectId:
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

    @overload
    def as_(self, type: Literal['tag']) -> Optional['ot.GitTagObject']: ...
    @overload
    def as_(self, type: Literal['commit']) -> Optional['ot.GitCommit']: ...
    @overload
    def as_(self, type: Literal['tree']) -> Optional['ot.GitTree']: ...
    @overload
    def as_(self, type: Literal['blob']) -> Optional['GitObject']: ...
    @overload
    def as_(self, type: GitObjectType) -> Optional['GitObject']: ...
    def as_(self, type: GitObjectType) -> Optional['GitObject']:
        """
        Return the object as the specified type, if possible.
        """
        if type == self.type:
            return self
        return None


#@runtime_checkable
class GitTree(GitObject, dict[str, 'et.GitEntry[EntryObject]']):
    """
    A git tree object.
    """
    @property
    def type(self) -> Literal['tree']:
        return 'tree'

    @property
    @abstractmethod
    def hash(self) -> TreeId: ...

    @property
    @abstractmethod
    def hashes(self) -> Mapping[ObjectId, IdentitySet['et.GitEntry', int]]: ...

    @abstractmethod
    def __getitem__(self, key: str) -> 'et.GitEntry[EntryObject]': ...

    @abstractmethod
    def __iter__(self) -> Iterator[str]:  ...

    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __contains__(self, key: object) -> bool: ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> et.GitEntry[EntryObject]: ...

    @abstractmethod
    def __eq__(self, other: Any) -> bool: ...

    @abstractmethod
    def __bool__(self) -> bool: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: 'CommitId|ot.GitCommit',
        name: str,
        mode: GitEntryMode,
        type: Literal['commit'],
        size: int,
        repository: 'ct.GitRepository',
        parent: Optional[GitObject] = None,
        parent_entry: Optional['et.GitEntryTree'] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, 'et.GitEntryCommit']: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: 'ot.BlobId|GitBlob',
        name: str,
        mode: GitEntryMode,
        type: Literal['blob'],
        size: int,
        repository: 'ct.GitRepository',
        parent: Optional[GitObject] = None,
        parent_entry: Optional['et.GitEntryTree'] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, 'et.GitEntryBlob']: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: 'TreeId|ot.GitTree',
        name: str,
        mode: GitEntryMode,
        type: Literal['tree'],
        size: int,
        repository: 'ct.GitRepository',
        parent: Optional[GitObject] = None,
        parent_entry: Optional['et.GitEntryTree'] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, 'et.GitEntryTree']: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: 'ObjectId|et.OBJ',
        name: str,
        mode: GitEntryMode,
        type: GitObjectType,
        size: int,
        repository: 'ct.GitRepository',
        parent: Optional[GitObject] = None,
        parent_entry: Optional['et.GitEntryTree'] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, 'et.GitEntry[et.OBJ]']: ...

    # Implementation
    def _git_entry(
        self,
        hash_or_obj: 'ObjectId|et.OBJ',
        name: str,
        mode: GitEntryMode,
        type: GitObjectType,
        size: int,
        repository: 'ct.GitRepository',
        parent: Optional[GitObject] = None,
        parent_entry: Optional['et.GitEntryTree'] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, 'et.GitEntry[et.OBJ]']:
        """
        Obtain or create a `GitObject` from a parsed entry line or equivalent.
        """
        ...

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
    def hash(self) -> BlobId: ...

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
    def stream(self) -> IO[str]:
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
    def hash(self) -> CommitId: ...

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
    def hash(self) -> TagId: ...

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
