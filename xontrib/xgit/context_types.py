'''
Types pertaining to the context of a git repository
and our operations on it.
'''

from pathlib import Path
from typing import Protocol, runtime_checkable, Optional

from xontrib.xgit.types import ContextKey
from xontrib.xgit.json_types import Jsonable
from xontrib.xgit.git_types import GitRef, GitCommit

@runtime_checkable
class GitRepository(Jsonable, Protocol):
    """
    A git repository.
    """

    path: Path = Path(".git")
    """
    The path to the common part of the repository. This is the same for all worktrees.
    """

    worktrees: dict[Path, 'GitWorktree']
    '''
    Worktrees known to be associated with this repository.
    '''
    def __getitem__(self, key: Path|str) -> 'GitWorktree': ...

    def get(self, key: Path|str) -> 'GitWorktree|None': ...


@runtime_checkable
class GitWorktree(Jsonable, Protocol):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """
    @property
    def repository(self) -> GitRepository: ...
    @property
    def repository_path(self) -> Path:
        """
        The path to the repository. If this is a separate worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `repository.path`.
        """
        ...
    @property
    def path(self) -> Path: ...
    branch: GitRef|None
    commit: GitCommit
    locked: str
    prunable: str

@runtime_checkable
class GitContext(Jsonable, Protocol):
    """
    A git context.
    """
    worktree: GitWorktree
    path: Path = Path(".")
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
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "GitContext":
        ...
