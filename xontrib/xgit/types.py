'''
Auxiliary types for xgit xontrib. These are primarily used for internal purposes.

Types for public use will be defined in the xgit module via `__init__.py`. and the
`__all__` variable.
'''

from pathlib import Path
from typing import (
     Generic, Literal, NewType, Optional, Protocol, TypeVar, ParamSpec
)

from xontrib.xgit.ids import ObjectId

try:
    from xontrib.xgit.type_aliases import (
        GitLoader,
        GitEntryMode,
        GitObjectType,
        GitObjectReference,
        JsonArray,
        JsonAtomic,
        JsonObject,
        JsonData,
        Directory,
        File,
        PythonFile,
        GitReferenceType, GitRepositoryId, GitObjectReference,
        KeywordArity, KeywordSpec, KeywordSpecs,
        KeywordInputSpec, KeywordInputSpecs,
        HeadingStrategy, ColumnKeys,
        list_of,
        DirectoryKind,
    )
except SyntaxError:
    from xontrib.xgit.type_aliases_310 import (
        GitLoader,
        GitEntryMode,
        GitObjectType,
        GitObjectReference,
        JsonArray,
        JsonAtomic,
        JsonObject,
        JsonData,
        Directory,
        File,
        PythonFile,
        GitReferenceType, GitObjectReference,
        KeywordArity, KeywordSpec, KeywordSpecs,
        KeywordInputSpec, KeywordInputSpecs,
        HeadingStrategy, ColumnKeys,
        DirectoryKind,
    )

if 'list_of' not in globals():
    globals()['list_of'] = lambda t: list
    globals()['list_of'].__doc__ = 'A type alias for a list of a type.'
    globals()['list_of'].__annotations__ = {'t': TypeVar('t')}
    globals()['list_of'].__module__ = __name__
    globals()['list_of'].__qualname__ = 'xontrib.xgit.types.list_of'
    globals()['list_of'].__name__ = 'list_of'

ObjectId = NewType('ObjectId', str)
'''
A git hash. Defined as a string to make the code more self-documenting.

Also allows using `GitHash` as a type hint that drives completion.
'''
CommitId = NewType('CommitId', ObjectId)
TagId = NewType('TagId', ObjectId)
TreeId = NewType('TreeId', ObjectId)
BlobId = NewType('BlobId', ObjectId)

GitRepositoryId = NewType('GitRepositoryId', str)
'''
A unique identifier for a git repository.

XOR of the commit IDs of every root commit.
'''

class _NoValue:
    """A type for a marker for a value that is not passed in."""
    __match_args__ = ()
    def __repr__(self):
        return '_NO_VALUE'


_NO_VALUE = _NoValue()
"""A marker value to indicate that a value was not supplied"""

S = TypeVar('S', contravariant=True)
V = TypeVar('V', covariant=True)
T = TypeVar('T')
P = ParamSpec('P')
class InitFn(Generic[S, V], Protocol):
    """
    A function that initializes a value from a source.
    """
    def __call__(self, source: S, /) -> V: ...


class ValueHandler(Protocol[S,V]):
    """
    A protocol for a value handle, such as the return from a command.
    """
    def __call__(self, value: S, /) -> V: ...

class GitException(Exception):
    """
    A base class for exceptions in the xgit xontrib.
    """
    def __init__(self, message: str, /):
        super().__init__(message)
        self.message = message

class GitNoSessionException(GitException):
    '''
    Thrown when attempting an operation that requires a session.
    '''
    name: str
    def __init__(self, name: str):
        super().__init__(f'No session is current for {name}.')
        self.name = name

class GitNoWorktreeException(GitException):
    '''
    Thrown when attempting an operation that requires a worktree.
    '''
    def __init__(self, message: Optional[str]=None):
        super().__init__(message or 'No worktree is current.')

class GitNoRepositoryException(GitNoWorktreeException):
    '''
    Thrown when attempting an operation that requires a repository,
    but we are not currently examining a repository.

    Implies `GitNoWorktreeException`.
    '''
    def __init__(self):
        super().__init__('No repository is current.')

class GitNoBranchException(GitException):
    '''
    Thrown when attempting an operation that requires a branch.
    '''
    def __init__(self):
        super().__init__('No branch is current.')

class GitError(GitException):
    '''
    Thrown when you an error is detected, other than not having a repo or worktree.
    '''

class GitValueError(GitError, ValueError):
    '''
    Thrown when a value supplied to Git is invalid.
    '''
    def __init__(self, message: str, /):
        super().__init__(message)
class GitDirNotFoundError(GitError):
    '''
    Thrown when a git directory is not found.
    '''
    path: Path
    kind: 'DirectoryKind'
    def __init__(self, path: Path, kind: 'DirectoryKind'='directory'):
        super().__init__(f'Git {kind} not found: {path}')
        self.path = path
        self.kind = kind

class WorktreeNotFoundError(GitDirNotFoundError):
    '''
    Thrown when a worktree is not found or is not a worktree.

    Implies `GitDirNotFoundError`.
    '''
    def __init__(self, path: Path):
        super().__init__(path, 'worktree')


class RepositoryNotFoundError(GitDirNotFoundError):
    '''
    Thrown when a repository is not found or is not a valid repository.

    Implies `GitDirNotFoundError`.
    '''
    def __init__(self, path: Path):
        super().__init__(path, 'repository')

