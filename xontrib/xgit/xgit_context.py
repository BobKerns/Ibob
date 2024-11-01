'''
Implementation of the `GitContext` class and related types.

* `GitContext` - a class that represents the context of our exploration
    of a git repository or worktree.
* `GitRepository` - a class that represents a git repository.
* `GitWorktree` - a class that represents a git worktree.
'''

from dataclasses import dataclass
from typing import Optional, Sequence, overload
from pathlib import Path
import sys

from xonsh.built_ins import XSH
from xonsh.tools import chdir
from xonsh.lib.pretty import PrettyPrinter

from xontrib.xgit.xgit_types import (
    GitContext,
    ContextKey,
    GitRepository,
    GitWorktree,
)
from xontrib.xgit.xgit_vars import XGIT_CONTEXTS
from xontrib.xgit.xgit_procs import (
    _run_stdout
)

@dataclass
class _GitRepository(GitRepository):
    """
    A git repository.
    """

    repository: Path = Path(".git")
    """
    The path to the repository. If this is a worktree,
    it is the path to the worktree-specific part.
    For the main worktree, this is the same as `common`.
    """
    common: Path = Path(".git")
    """
    The path to the common part of the repository. This is the same for all worktrees.
    """


@dataclass
class _GitWorktree(_GitRepository, GitWorktree):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """

    worktree: Path | None = Path(".")


@dataclass
class _GitContext(_GitWorktree, GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    git_path: Path = Path(".")
    branch: str = ""
    commit: str = ""

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        subpath = Path(subpath) if subpath else None
        key = self.worktree or self.repository
        if subpath is None:
            return (key, self.git_path, self.branch, self.commit)
        return (key, subpath, self.branch, self.commit)

    @property
    def cwd(self) -> Path:
        return Path.cwd()

    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        common: Optional[Path] = None,
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "_GitContext":
        worktree = worktree or self.worktree
        repository = repository or self.repository
        common = common or self.common
        git_path = git_path or self.git_path
        branch = branch if branch is not None else self.branch
        commit = commit or self.commit
        return _GitContext(
            worktree=worktree,
            repository=repository,
            common=common,
            git_path=git_path,
            branch=branch,
            commit=commit,
        )

    def _repr_pretty_(self, p: PrettyPrinter, cycle: bool):
        if cycle:
            p.text(f"GitContext({self.worktree} {self.git_path}")
        else:
            with p.group(4, "GitTree:"):
                p.break_()
                wt = _relative_to_home(self.worktree) if self.worktree else None
                p.text(f"worktree: {wt}")
                p.break_()
                p.text(f"repository: {_relative_to_home(self.repository)}")
                p.break_()
                p.text(f"common: {_relative_to_home(self.common)}")
                p.break_()
                p.text(f"path: {self.git_path}")
                p.break_()
                p.text(f"branch: {self.branch}")
                p.break_()
                p.text(f"commit: {self.commit}")
                p.break_()
                p.text(f"cwd: {_relative_to_home(Path.cwd())}")


def _relative_to_home(path: Path) -> Path:
    """
    Get a path for display relative to the home directory.
    This is for display only.
    """
    home = Path.home()
    if path == home:
        return Path("~")
    if path == home.parent:
        return Path(f"~{home.name}")
    try:
        return Path("~") / path.relative_to(home)
    except ValueError:
        return path


def _git_context():
    """
    Get the git context based on the current working directory,
    updating it if necessary.

    The result should generally be passed to `_set_xgit`.
    """

    @overload
    def multi_params(params: str, /) -> str: ...

    @overload
    def multi_params(param: str, *params: str) -> Sequence[str]: ...

    def multi_params(*params: str) -> Sequence[str] | str:
        """
        Use `git rev-parse` to get multiple parameters at once.
        """
        val = _run_stdout(["git", "rev-parse", *params])
        if val:
            result = val.strip().split("\n")
        else:
            # Try running them individually.
            result = [_run_stdout(["git", "rev-parse", param]) for param in params]
        if len(result) == 1:
            # Otherwise we have to assign like `value, = multi_params(...)`
            # The comma is` necessary to unpack the single value
            # but is confusing and easy to forget
            # (or not understand if you don't know the syntax).
            return result[0]
        return result

    in_tree, in_git = multi_params("--is-inside-work-tree", "--is-inside-git-dir")
    try:
        if in_tree == "true":
            # Inside a worktree
            worktree, repository, common, commit = multi_params(
                "--show-toplevel",
                "--absolute-git-dir",
                "--git-common-dir",
                "HEAD",
            )
            worktree = Path(worktree).resolve()
            repository = Path(repository)
            common = repository / common
            git_path = Path.cwd().relative_to(worktree)
            branch = XSH.subproc_captured_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            if worktree in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[worktree]
                xgit.git_path = git_path
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                return _GitContext(
                    worktree=worktree,
                    repository=repository,
                    common=common,
                    git_path=git_path,
                    commit=commit,
                    branch=branch,
                )
        elif in_git == "true":
            # Inside a .git directory or bare repository.
            repository, common = multi_params("--absolute-git-dir", "--git-common-dir")
            repository = Path(repository).resolve()
            common = repository / common
            with chdir(common.parent):
                worktree = multi_params("--show-toplevel")
                worktree = Path(worktree).resolve() if worktree else None
            commits = multi_params("HEAD", "main", "master")
            commits = list(filter(lambda x: x, list(commits)))
            commit = commits[0] if commits else ""
            branch = XSH.subproc_captured_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            repo = worktree or repository
            if repo in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[repo]
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                return _GitContext(
                    worktree=worktree,
                    repository=repository,
                    common=common,
                    git_path=Path("."),
                    commit=commit,
                    branch=branch,
                )
        else:
            return None
    except Exception as ex:
        if XSH.env.get("XGIT_TRACE_ERRORS"):
            import traceback
            traceback.print_exc()
        print(f"Error setting git context: {ex}", file=sys.stderr)
    return None

