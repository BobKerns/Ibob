'''
Types for xgit references.
'''

from abc import abstractmethod
from typing import (
    Protocol, TypeAlias, runtime_checkable, TYPE_CHECKING,
)

from xontrib.xgit.types import ObjectId

if TYPE_CHECKING:
    import xontrib.xgit.context_types as ct
    import xontrib.xgit.object_types as ot
    from collections.abc import Sequence
    from pathlib import PurePosixPath


RefSpec: TypeAlias = 'PurePosixPath|str|Sequence[RefSpec]|GitRef'
'''
Ways to specify a ref. A sequence is searched for the first valid ref.
'''

@runtime_checkable
class GitRef(Protocol):
    """
    Any ref, usually a branch or tag, usually pointing to a commit.
    """
    @property
    @abstractmethod
    def name(self) -> str: ...
    @property
    @abstractmethod
    def target(self) -> 'ot.GitObject': ...
    @property
    @abstractmethod
    def repository(self) -> 'ct.GitRepository': ...

@runtime_checkable
class Branch(GitRef, Protocol):
    """
    A branch ref. These are simply refs that live in the refs/heads namespace.
    They should always refer to a commit.
    """
    @abstractmethod
    def branch_name(self) -> str:
        '''
        The name of the branch, without the refs/branch prefix
        '''

@runtime_checkable
class RemoteBranch(GitRef, Protocol):
    """
    A branch ref that lives in the refs/remotes namespace. These should always
    refer to a commit, and track what is known locally about what is happening
    on a remote branch. They are updated by `git fetch` (and `git pull`, which
    does a `git fetch`), and by `git push`.
    """
    @abstractmethod
    def remote_branch_name(self) -> str:
        '''
        The name of the remote branch, without the refs/remotes prefix
        '''

@runtime_checkable
class Tag(GitRef, Protocol):
    """
    A tag ref. These are simply refs that live in the refs/tags namespace.
    """
    @abstractmethod
    def tag_name(self) -> str:
        '''
        The name of the tag, without the refs/tags prefix
        '''

@runtime_checkable
class Replacement(GitRef, Protocol):
    """
    A replacement ref. These are refs that live in the refs/replace namespace.
    Their name will be the hash of the object they replace, and their target
    is the replacement object
    """
    @property
    @abstractmethod
    def replacement_name(self) -> ObjectId:
        "The Sha1 hash of the object being replaced."

    @property
    @abstractmethod
    def replaced_object(self) -> 'ot.GitObject':
        "The object being replaced."

    @property
    @abstractmethod
    def replacement_object(self) -> 'ot.GitObject':
        "The object that replaces the replaced object."

@runtime_checkable
class Note(GitRef, Protocol):
    '''
    A note ref. These are refs that live in the refs/notes namespace.
    '''
    @property
    @abstractmethod
    def note_name(self) -> str:
        '''
        The name of the note, without the refs/notes prefix
        '''
    @property
    @abstractmethod
    def note_target(self) -> 'ot.GitObject':
        '''
        The object the note is attached to.
        '''
    @property
    @abstractmethod
    def text(self) -> str:
        '''
        The text of the note.
        '''