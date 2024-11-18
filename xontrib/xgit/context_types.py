'''
Types pertaining to the context of a git repository
and our operations on it.
'''

from abc import abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable, Optional

from xontrib.xgit.types import ContextKey
from xontrib.xgit.json_types import Jsonable
import xontrib.xgit.git_types as gt

@runtime_checkable
class GitRepository(Jsonable, Protocol):
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
    def __getitem__(self, key: Path|str) -> 'GitWorktree': ...

    def get(self, key: Path|str) -> 'GitWorktree|None': ...


@runtime_checkable
class GitWorktree(Jsonable, Protocol):
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
    def branch(self) -> 'gt.GitRef': ...
    @branch.setter
    @abstractmethod
    def branch(self, value: 'gt.GitRef|str|None'): ...
    @property
    @abstractmethod
    def commit(self) -> 'gt.GitCommit': ...
    @commit.setter
    @abstractmethod
    def commit(self, value: 'gt.GitCommit|str'): ...
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
    def path(self) -> Path: ...
    @path.setter
    @abstractmethod
    def path(self, value: Path|str): ...
    @property
    @abstractmethod
    def branch(self) -> 'gt.GitRef': ...
    @branch.setter
    @abstractmethod
    def branch(self, value: 'gt.GitRef|str'): ...
    @property
    @abstractmethod
    def commit(self) -> 'gt.GitCommit': ...
    @commit.setter
    @abstractmethod
    def commit(self, value: 'gt.GitCommit|str'): ...
    @property
    @abstractmethod
    def cwd(self) -> Path: ...

    @property
    def root(self) -> 'gt.GitTreeEntry': ...

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
