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
from io import IOBase
from pathlib import Path
from typing import Iterator, Protocol, Sequence, overload, runtime_checkable, Optional

from xontrib.xgit.types import ContextKey
from xontrib.xgit.json_types import Jsonable
import xontrib.xgit.object_types as ot
import xontrib.xgit.entry_types as et
import xontrib.xgit.ref_types as rt

@runtime_checkable
class GitCmd(Protocol):
    '''
    Context for git commands.
    '''
    @abstractmethod
    def git(self, *args, **kwargs) -> str: ...
    @abstractmethod
    def git_lines(self, *args, **kwargs) -> list[str]: ...
    @abstractmethod
    def git_stream(self, *args, **kwargs) -> Iterator[str]: ...
    @abstractmethod
    def git_binary(self, *args, **kwargs) -> IOBase: ...

    @overload
    def rev_parse(self, params: str, /) -> str: ...
    @overload
    def rev_parse(self,param: str, *_params: str) -> Sequence[str]: ...
    @abstractmethod
    def rev_parse(self, param: str, *params: str) -> Sequence[str] | str: ...


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

    def get_worktree(self, key: Path|str) -> 'GitWorktree|None':
        '''
        Get a worktree by its path. Canonicalizes the path first,
        making this the preferred way to get a worktree.
        '''



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
    def path(self) -> Path: ...
    @path.setter
    @abstractmethod
    def path(self, value: Path|str): ...
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

    @property
    def root(self) -> 'et.GitEntryTree': ...

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        ...

    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "GitContext":
        ...
