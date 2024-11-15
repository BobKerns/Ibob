'''
Implementation of the `GitContext` class and related types.

* `GitContext` - a class that represents the context of our exploration
    of a git repository or worktree.
* `GitRepository` - a class that represents a git repository.
* `GitWorktree` - a class that represents a git worktree.
'''

from dataclasses import dataclass
from typing import MutableMapping, Optional, Sequence, overload
from pathlib import Path
import sys

from xonsh.tools import chdir
from xonsh.lib.pretty import PrettyPrinter

from xontrib.xgit.to_json import JsonDescriber
from xontrib.xgit.types import (
    GitContext,
    ContextKey,
    GitRepository,
    GitWorktree,
    GitCommit,
)
from xontrib.xgit.vars import XGIT_CONTEXTS, XSH
from xontrib.xgit.procs import (
    _run_stdout, _run_text,
)
from xontrib.xgit.objects import _git_object

@dataclass
class _GitRepository(GitRepository):
    """
    A git repository.
    """

    _repository: Path = Path(".git")
    @property
    def repository(self) -> Path:
        return self._repository

    @repository.setter
    def repository(self, value: Path|str):
        self._repository = Path(value)
    """
    The path to the repository. If this is a worktree,
    it is the path to the worktree-specific part.
    For the main worktree, this is the same as `common`.
    """

    _common: Path = Path(".git")
    @property
    def common(self) -> Path:
        return self._common
    @common.setter
    def common(self, value: Path|str):
        self._common = Path(value)


    """
    The path to the common part of the repository. This is the same for all worktrees.
    """

    def __init__(self, *args,
                 repository: Path = Path(".git"),
                 common: Path = Path('.git'),
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.repository = repository
        self.common = common

    def to_json(self, describer: JsonDescriber):
        return {
            "repository": describer.to_json(self.repository),
            "common": describer.to_json(self.common),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitRepository(
            repository=describer.from_json(data["repository"]),
            common=describer.from_json(data["common"]),
        )

@dataclass
class _GitWorktree(_GitRepository, GitWorktree):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """

    _worktree: Path | None = Path(".")
    @property
    def worktree(self) -> Path | None:
        return self._worktree
    @worktree.setter
    def worktree(self, value: Path | str | None):
        self._worktree = Path(value) if value else None

    def __init__(self, *args,
                    worktree: Path | None = Path("."),
                    **kwargs):
            super().__init__(*args, **kwargs)
            self.worktree = worktree

    def to_json(self, describer: JsonDescriber):
        return {
            "worktree": describer.to_json(self.worktree),
            "repository": describer.to_json(self.repository),
            "common": describer.to_json(self.common),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitWorktree(
            worktree=describer.from_json(data["worktree"]),
            repository=describer.from_json(data["repository"]),
            common=describer.from_json(data["common"]),
        )


@dataclass
class _GitContext(_GitWorktree, GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    _git_path: Path = Path(".")
    @property
    def git_path(self) -> Path:
        return self._git_path

    @git_path.setter
    def git_path(self, value: Path|str):
        self._git_path = Path(value)

    branch: str = ""
    _commit: GitCommit|None = None
    @property
    def commit(self) -> GitCommit:
        assert self._commit is not None, "Commit has not been set."
        return self._commit

    @commit.setter
    def commit(self, value: str|GitCommit):
        match value:
            case str():
                hash = _run_text(['git', 'rev-parse', value]).strip()
                self._commit = _git_object(hash, 'commit', self)
            case GitCommit():
                self._commit = value
            case _:
                raise ValueError(f'Not a commit: {value}')

    def __init__(self, *args,
                 git_path: Path = Path("."),
                 branch: str = "",
                 commit: str|GitCommit = 'HEAD',
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.commit = commit
        self._git_path = git_path
        self.branch = branch

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        subpath = Path(subpath) if subpath else None
        key = self.worktree or self._repository
        commit = self.commit
        hash = '''
        if commit is not None:
            hash = commit.hash
        '''
        if subpath is None:
            return (key, self._git_path, self.branch, hash)
        return (key, subpath, self.branch, hash)

    @property
    def cwd(self) -> Path:
        return Path.cwd()
    @cwd.setter
    def cwd(self, value: Path|str):
        chdir(Path(value))

    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        common: Optional[Path] = None,
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str|GitCommit] = None,
    ) -> "_GitContext":
        worktree = worktree or self.worktree
        repository = repository or self._repository
        common = common or self.common
        git_path = git_path or self._git_path
        branch = branch if branch is not None else self.branch
        if isinstance(commit, str):
            commit = _git_object(commit, 'commit', self)
        commit = commit or self.commit
        return _GitContext(
            worktree=worktree,
            _repository=repository,
            common=common,
            git_path=git_path,
            branch=branch,
            commit=commit,
        )

    def _repr_pretty_(self, p: PrettyPrinter, cycle: bool):
        if cycle:
            p.text(f"GitContext({self.worktree} {self._git_path}")
        else:
            assert self.commit is not None, "Commit has not been set"
            with p.group(4, "GitTree:"):
                p.break_()
                wt = _relative_to_home(self.worktree) if self.worktree else None
                p.text(f"worktree: {wt}")
                with p.group(2):
                    p.break_()
                    p.text(f"repository: {_relative_to_home(self._repository)}")
                    p.break_()
                    p.text(f"common: {_relative_to_home(self.common)}")
                    p.break_()
                    p.text(f"git_path: {self.git_path}")
                    p.break_()
                    p.text(f"branch: {self.branch}")
                p.break_()
                p.text(f"commit: {self.commit.hash}")
                with p.group(2):
                    p.break_()
                    p.text(f'{self.commit.author} {self.commit.author_date}')
                    p.break_()
                    p.text(self.commit.message)
                p.break_()
                p.text(f"cwd: {_relative_to_home(Path.cwd())}")

    def to_json(self, describer: JsonDescriber):
        assert self.commit is not None, "Commit has not been set"
        return {
            "worktree": describer.to_json(self.worktree),
            "repository": describer.to_json(self._repository),
            "common": describer.to_json(self.common),
            "git_path": describer.to_json(self.git_path),
            "branch": describer.to_json(self.branch),
            "commit": describer.to_json(self.commit.hash),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitContext(
            worktree=describer.from_json(data["worktree"]),
            _repository=describer.from_json(data["repository"]),
            common=describer.from_json(data["common"]),
            git_path=describer.from_json(data["git_path"]),
            branch=describer.from_json(data["branch"]),
            commit=describer.from_json(data["commit"]),
        )


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


@overload
def multi_params(params: str, /) -> str: ...
@overload
def multi_params(param: str, *_params: str) -> Sequence[str]: ...
def multi_params(param: str, *params: str) -> Sequence[str] | str:
    """
    Use `git rev-parse` to get multiple parameters at once.
    """
    all_params = [param, *params]
    val = _run_stdout(["git", "rev-parse", *all_params])
    if val:
        # Drop the last line, which is empty.
        result = val.split("\n")[:-1]
    else:
        # Try running them individually.
        result = [_run_stdout(["git", "rev-parse", param]) for param in all_params]
    if len(params)+1 == 1:
        # Otherwise we have to assign like `value, = multi_params(...)`
        # The comma is` necessary to unpack the single value
        # but is confusing and easy to forget
        # (or not understand if you don't know the syntax).
        return result[0]
    return result


def _git_context():
    """
    Get the git context based on the current working directory,
    updating it if necessary.

    The result should generally be passed to `_set_xgit`.
    """
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
            branch = _run_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            key = worktree or repository
            if key in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[key]
                xgit.git_path = git_path
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                gctx = _GitContext(
                    worktree=worktree,
                    _repository=repository,
                    common=common,
                    git_path=git_path,
                    commit=_git_object(commit, 'commit'),
                    branch=branch,
                )
                XGIT_CONTEXTS[key] = gctx
                return gctx
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
            branch = _run_stdout(
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
                    _repository=repository,
                    common=common,
                    git_path=Path("."),
                    commit=_git_object(commit, 'commit'),
                    branch=branch,
                )
        else:
            return None
    except Exception as ex:
        env = XSH.env
        assert isinstance(env, MutableMapping),\
            f"XSH.env is not a MutableMapping: {env!r}"
        if env.get("XGIT_TRACE_ERRORS"):
            import traceback
            traceback.print_exc()
        print(f"Error setting git context: {ex}", file=sys.stderr)
    return None

