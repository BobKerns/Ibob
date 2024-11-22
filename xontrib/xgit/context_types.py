'''
Types pertaining to the context of a git repository and our operations on it.

The key types are:
- `GitWorktree`: The root directory of where the files are checked out.
- `GitRepository`: The common part of the repository. This is the same for all
    worktrees associated with a repository.
- `GitContext`: The context for git commands.
    This includes the worktree and its repository, but also the current branch,
    commit, and path within the worktree/GitTree that we are exploring.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from abc import abstractmethod
from ast import TypeAlias
from pathlib import Path, PurePosixPath
from typing import (
    Literal, Protocol, overload, runtime_checkable, Optional, TypeAlias, TYPE_CHECKING
)

from xontrib.xgit.types import ContextKey, GitObjectType
from xontrib.xgit.json_types import Jsonable
from xontrib.xgit.git_cmd import GitCmd
import xontrib.xgit.object_types as ot
import xontrib.xgit.ref_types as rt
if TYPE_CHECKING:
    from xontrib.xgit.context_types import GitWorktree


WorktreeMap: TypeAlias = dict[Path, 'GitWorktree']


@runtime_checkable
class GitRepository(Jsonable, GitCmd, Protocol):
    """
    A git repository.
    """
    @property
    @abstractmethod
    def path(self) -> Path:
        """
        The path to the common part of the repository. This is the same for all worktrees.
        """
        ...

    @property
    @abstractmethod
    def worktree(self) -> 'GitWorktree': ...

    @property
    @abstractmethod
    def worktrees(self) -> dict[Path, 'GitWorktree']:
        '''
        Worktrees known to be associated with this repository.
        '''
        ...

    @abstractmethod
    def get_worktree(self, key: Path|str) -> 'GitWorktree|None':
        '''
        Get a worktree by its path. Canonicalizes the path first,
        making this the preferred way to get a worktree.
        '''

    @abstractmethod
    def get_reference(self, ref: 'rt.RefSpec|None' =None) -> 'rt.GitRef|None':
        '''
        Get a reference by name.
        '''

    @overload
    def get_object(self, hash: 'ot.Commitish', type: Literal['commit']) -> 'ot.GitCommit':
        ...
    @overload
    def get_object(self, hash: 'ot.Treeish', type: Literal['tree']) -> 'ot.GitTree':
        ...
    @overload
    def get_object(self, hash: 'ot.Blobish', type: Literal['blob'],
                   size: int=-1) -> 'ot.GitBlob':
        ...
    @overload
    def get_object(self, hash: 'ot.Tagish', type: Literal['tag']) -> 'ot.GitTagObject':
        ...
    @overload
    def get_object(self, hash: 'ot.Objectish',
                   type: Optional[GitObjectType]=None,
                   size: int=-1) -> 'ot.GitObject':
        ...
    def get_object(self, hash: 'ot.Objectish',
                   type: Optional[GitObjectType]=None,
                   size: int=-1) -> 'ot.GitObject':
        ...

@runtime_checkable
class GitWorktree(Jsonable, GitCmd, Protocol):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """
    @property
    @abstractmethod
    def repository(self) -> GitRepository: ...
    @property
    @abstractmethod
    def repository_path(self) -> Path:
        """
        The path to the repository. If this is a separate worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `repository.path`.
        """
        ...
    @property
    @abstractmethod
    def path(self) -> Path: ...
    @property
    @abstractmethod
    def branch(self) -> 'rt.GitRef': ...
    @branch.setter
    @abstractmethod
    def branch(self, value: 'rt.GitRef|str|None'): ...
    @property
    @abstractmethod
    def commit(self) -> 'ot.GitCommit': ...
    @commit.setter
    @abstractmethod
    def commit(self, value: 'ot.GitCommit|str'): ...
    locked: str
    prunable: str

@runtime_checkable
class GitContext(Jsonable, Protocol):
    """
    A git context.
    """
    @property
    @abstractmethod
    def worktree(self) -> GitWorktree: ...
    @property
    @abstractmethod
    def repository(self) -> GitRepository: ...
    @property
    @abstractmethod
    def path(self) -> PurePosixPath: ...
    @path.setter
    @abstractmethod
    def path(self, value: PurePosixPath|str): ...
    @property
    @abstractmethod
    def branch(self) -> 'rt.GitRef': ...
    @branch.setter
    @abstractmethod
    def branch(self, value: 'rt.GitRef|str'): ...
    @property
    @abstractmethod
    def commit(self) -> 'ot.GitCommit': ...
    @commit.setter
    @abstractmethod
    def commit(self, value: 'ot.GitCommit|str'): ...
    @property
    @abstractmethod
    def cwd(self) -> Path: ...

    #@property
    #def root(self) -> 'et.GitEntryTree': ...

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        ...

    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        git_path: Optional[PurePosixPath] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "GitContext":
        ...
