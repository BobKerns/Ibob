'''
Implementation of the `GitContext` class and related types.

* `GitContext` - a class that represents the context of our exploration
    of a git repository or worktree.
* `GitRepository` - a class that represents a git repository.
* `GitWorktree` - a class that represents a git worktree.
'''

from dataclasses import dataclass, field
from operator import call
import re
from typing import (
    MutableMapping, Optional, Sequence, TypeAlias, cast, overload, Mapping,
)
from pathlib import Path
import sys
from types import MappingProxyType

from xonsh.tools import chdir
from xonsh.lib.pretty import PrettyPrinter

from xontrib.xgit.ref import _GitRef
from xontrib.xgit.to_json import JsonDescriber
from xontrib.xgit.types import ContextKey, InitFn, GitHash
from xontrib.xgit.git_types import GitObject, GitRef, GitTagObject, GitCommit
from xontrib.xgit.context_types import (
    GitContext,
    GitRepository,
    GitWorktree
)
from xontrib.xgit.vars import (
    XGIT_CONTEXTS, XSH, XGIT_REPOSITORIES, XGIT_WORKTREES,
)
from xontrib.xgit.procs import (
    _run_stdout, _run_text, _run_lines,
)
from xontrib.xgit.objects import _git_object
from xontrib.xgit.ref import _GitRef

DEFAULT_BRANCH="HEAD"

WorktreeMap: TypeAlias = dict[Path, GitWorktree]
@dataclass
class _GitRepository(GitRepository):
    """
    A git repository.
    """

    _path: Path
    @property
    def path(self) -> Path:
        """
        The path to the repository. If this is a worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `common`.
        """
        return self._path

    _worktrees: WorktreeMap|InitFn['_GitRepository',WorktreeMap] = field(default_factory=dict)
    @property
    def worktrees(self) -> Mapping[Path, GitWorktree]:
        if callable(self._worktrees):
            self._worktrees = self._worktrees(self)
        return MappingProxyType(self._worktrees)

    def __getitem__(self, key: Path|str) -> GitWorktree:
        if callable(self._worktrees):
            self._worktrees = self._worktrees(self)
        key = Path(key).resolve()
        worktree = self._worktrees.get(key)
        if worktree is None:
            branch_name = _run_stdout(['git', 'symbolic-ref', 'q', 'HEAD'])
            branch = _GitRef(branch_name) if branch_name else None
            commit = _git_object('HEAD', 'commit')  # Should be the same as branch.target
            worktree = _GitWorktree(
                path=Path(key),
                repository=self,
                repository_path=self.path,
                branch=branch,
                commit=commit,
                locked='',
                prunable='',
            )
            self._worktrees[key] = worktree
        return worktree

    def get(self, key: Path|str) -> GitWorktree|None:
        if callable(self._worktrees):
            self._worktrees = self._worktrees(self)
        return self._worktrees.get(Path(key).resolve())

    _objects: dict[GitHash, GitObject] = field(default_factory=dict)


    """
    The path to the common part of the repository. This is the same for all worktrees.
    """

    def __init__(self, *args,
                 path: Path = Path(".git"),
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._path = path
        def init_worktrees(self: _GitRepository) -> WorktreeMap:
            bare: bool = False
            result: dict[Path,GitWorktree] = {}
            worktree: Path = path.parent
            branch: GitRef|None = None
            commit: GitCommit|None = None
            locked: str = ''
            prunable: str = ''
            for l in _run_lines(['git', 'worktree', 'list', '--porcelain']):
                match l.strip().split(' ', maxsplit=1):
                    case ['worktree', wt]:
                        worktree = Path(wt)
                    case ['HEAD', c]:
                        commit = _git_object(c, 'commit')
                        self._objects[commit.hash] = commit
                    case ['branch', b]:
                        branch = _GitRef(b)
                    case ['locked', l]:
                        locked = l.strip('"')
                        locked = locked.replace('\\n', '\n')
                        locked = locked.replace('\\"', '"')
                        locked =locked.replace('\\\\', '\\')
                    case ['locked']:
                        locked = '-'''
                    case ['prunable', p]:
                        prunable = p.strip('"')
                        prunable = prunable.replace('\\n', '\n')
                        prunable = prunable.replace('\\"', '"')
                        prunable =prunable.replace('\\\\', '\\')
                    case ['prunable']:
                        prunable = '-'''
                    case ['detached']:
                        branch = None
                    case ['bare']:
                        bare = True
                    case []:
                        with chdir(worktree):
                            repository_path = Path(_run_stdout(['git', 'rev-parse', '--show-toplevel']))
                        assert commit is not None, "Commit has not been set."
                        result[worktree] = _GitWorktree(
                            path=worktree,
                            repository=self,
                            repository_path=repository_path,
                            branch=branch,
                            commit=commit,
                            locked=locked,
                            prunable=prunable,
                        )
                        worktree = path.parent
                        branch = None
                        commit = None
                        locked = ''
                        prunable = ''
            return result
        self._worktrees = init_worktrees
        self._objects = {}

    def to_json(self, describer: JsonDescriber):
        return {
            "path": describer.to_json(self.path),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitRepository(
            repository=describer.from_json(data["repository"]),
        )

class _GitWorktree(GitWorktree):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """
    _repository: GitRepository
    @property
    def repository(self) -> GitRepository:
        return self._repository

    _repository_path: Path
    @property
    def repository_path(self) -> Path:
        """
        The path to the repository. If this is a separate worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `repository.path`.
        """
        return self._repository_path

    _path: Path | None = Path(".")
    @property
    def path(self) -> Path | None:
        return self._path

    branch: GitRef|None
    commit: GitCommit
    locked: str
    prunable: str

    def __init__(self, *args,
                    repository: GitRepository,
                    path: Path ,
                    repository_path: Path,
                    branch: GitRef|None,
                    commit: GitCommit,
                    locked: str,
                    prunable: str,
                    **kwargs):
            super().__init__(*args, **kwargs)
            self._repository = repository
            self._path = path
            self._repository_path = repository_path
            self.branch = branch
            self.commit = commit
            self.locked = locked
            self.prunable = prunable

    def to_json(self, describer: JsonDescriber):
        return {
            "repository": describer.to_json(self.repository),
            "repository_path": describer.to_json(self.repository_path),
            "path": describer.to_json(self.path),
            "branch": describer.to_json(self.branch),
            "commit": describer.to_json(self.commit),
            "locked": describer.to_json(self.locked),
            "prunable": describer.to_json(self.prunable),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitWorktree(
            repository=describer.from_json(data["repository"]),
            repository_path=describer.from_json(data["repository_path"]),
            path=describer.from_json(data["path"]),
            branch=describer.from_json(data["branch"]),
            commit=describer.from_json(data["commit"]),
            locked=describer.from_json(data["locked"]),
            prunable=describer.from_json(data["prunable"]),
        )


@dataclass
class _GitContext(GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    _worktree: GitWorktree
    @property
    def worktree(self) -> GitWorktree:
        return self._worktree

    _path: Path = Path(".")
    @property
    def path(self) -> Path:
        return self._path

    @path.setter
    def path(self, value: Path|str):
        self._path = Path(value)

    _branch: _GitRef = _GitRef(DEFAULT_BRANCH)
    @property
    def branch(self) -> _GitRef:
        return self._branch
    @branch.setter
    def branch(self, value: str|_GitRef):
        match value:
            case _GitRef():
                self._branch = value
            case str():
                self._branch = _GitRef(value)
            case _:
                raise ValueError(f"Invalid branch: {value!r}")
    _commit: GitCommit|None = None
    @property
    def commit(self) -> GitCommit:
        assert self._commit is not None, "Commit has not been set."
        return self._commit

    @commit.setter
    def commit(self, value: str|GitCommit|_GitRef|GitTagObject):
        match value:
            case str():
                hash = _run_text(['git', 'rev-parse', value]).strip()
                self._commit = _git_object(hash, 'commit', self)
            case GitCommit():
                self._commit = value
            case GitTagObject():
                # recurse if necessary to get the commit
                # or error if the tag doesn't point to a commit
                self.commit = cast(GitCommit, value.object)
            case _GitRef():
                # recurse if necessary to get the commit
                # or error if the ref doesn't point to a commit
                self.commit = cast(GitCommit, value.target)
            case _:
                raise ValueError(f'Not a commit: {value}')

    def __init__(self, *args,
                 worktree: GitWorktree,
                 path: Path = Path("."),
                 branch: str|_GitRef = DEFAULT_BRANCH,
                 commit: str|GitCommit = DEFAULT_BRANCH,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._worktree = worktree
        self.commit = commit
        self._path = path
        self.branch = branch

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        subpath = Path(subpath) if subpath else None
        key = self.worktree.path
        commit = self.commit
        hash = '''
        if commit is not None:
            hash = commit.hash
        '''
        if subpath is None:
            return (key, self._path, self.branch.name, hash)
        return (key, subpath, self.branch.name, hash)

    @property
    def cwd(self) -> Path:
        return Path.cwd()
    @cwd.setter
    def cwd(self, value: Path|str):
        chdir(Path(value))

    def new_context(
        self,
        /,
        worktree: Optional[GitWorktree] = None,
        path: Optional[Path] = None,
        branch: Optional[str|_GitRef] = None,
        commit: Optional[str|GitCommit] = None,
    ) -> "_GitContext":
        worktree = worktree or self.worktree
        path = path or self._path
        branch = branch if branch is not None else self.branch
        if isinstance(commit, str):
            commit = _git_object(commit, 'commit', self)
        commit = commit or self.commit
        return _GitContext(
            worktree=worktree,
            path=path,
            branch=branch,
            commit=commit,
        )

    def _repr_pretty_(self, p: PrettyPrinter, cycle: bool):
        if cycle:
            p.text(f"GitContext({self.worktree} {self.path}")
        else:
            assert self.commit is not None, "Commit has not been set"
            with p.group(4, "Context:"):
                p.break_()
                wt = _relative_to_home(self.worktree.path)
                p.text(f"worktree: {wt}")
                with p.group(2):
                    p.break_()
                    p.text(f"repository: {_relative_to_home(self.worktree.repository_path)}")
                    p.break_()
                    p.text(f"common: {_relative_to_home(self.worktree.repository.path)}")
                p.break_()
                p.text(f"git_path: {self.path}")
                p.break_()
                p.text(f"branch: {self.branch}")
                p.break_()
                p.text(f"commit: {self.commit.hash}")
                with p.group(2):
                    p.break_()
                    p.text(f'{self.commit.author} {self.commit.author_date}')
                    for line in self.commit.message.splitlines():
                        p.break_()
                        p.text(line)
                p.break_()
                p.text(f"cwd: {_relative_to_home(Path.cwd())}")

    def to_json(self, describer: JsonDescriber):
        assert self.commit is not None, "Commit has not been set"
        return {
            "worktree": describer.to_json(self.worktree),
            "path": describer.to_json(self.path),
            "branch": describer.to_json(self.branch),
            "commit": describer.to_json(self.commit.hash),
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        return _GitContext(
            worktree=describer.from_json(data["worktree"]),
            path=describer.from_json(data["git_path"]),
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
            worktree_path, repository_path, common, commit = multi_params(
                "--show-toplevel",
                "--absolute-git-dir",
                "--git-common-dir",
                "HEAD",
            )
            worktree_path = Path(worktree_path).resolve()
            repository_path = Path(repository_path).resolve()
            common = Path(common).resolve()
            repository = _GitRepository(path=common)
            worktree: GitWorktree = repository[worktree_path]


            path = Path.cwd().relative_to(worktree_path)
            branch = _run_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            key = worktree_path or repository_path
            if key in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[key]
                xgit.path = path
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                if worktree_path in XGIT_WORKTREES:
                    worktree = XGIT_WORKTREES[worktree_path]
                    gctx = _GitContext(
                        worktree=worktree,
                        path=path,
                        commit=_git_object(commit, 'commit'),
                        branch=branch,
                    )
                    XGIT_CONTEXTS[key] = gctx
                    return gctx
                elif repository_path in XGIT_REPOSITORIES:
                    repository = XGIT_REPOSITORIES[repository_path]
                    worktree = _GitWorktree(
                        path=worktree_path,
                        repository=repository,
                        repository_path=repository_path,
                        branch=_GitRef(branch),
                        commit=_git_object(commit, 'commit'),
                        locked='',
                        prunable='',
                    )
                    XGIT_WORKTREES[worktree_path] = worktree
                    gctx = _GitContext(
                        worktree=worktree,
                        path=path,
                        commit=_git_object(commit, 'commit'),
                        branch=branch,
                    )
                    XGIT_CONTEXTS[key] = gctx
                    return gctx
                else:
                    repository = _GitRepository(path=common)
                    XGIT_REPOSITORIES[repository_path] = repository
                    worktree = _GitWorktree(
                        path=worktree_path,
                        repository=repository,
                        repository_path=repository_path,
                        branch=_GitRef(branch),
                        commit=_git_object(commit, 'commit'),
                        locked='',
                        prunable='',
                    )
                    XGIT_WORKTREES[worktree_path] = worktree
                    xgit = _GitContext(
                        worktree=worktree,
                        path=path,
                        commit=_git_object(commit, 'commit'),
                        branch=branch,
                    )
                    XGIT_CONTEXTS[key] = xgit
                    return xgit
        elif in_git == "true":
            # Inside a .git directory or bare repository.
            repository_path, common = multi_params("--absolute-git-dir", "--git-common-dir")
            repository_path = Path(repository_path).resolve()
            common = repository_path / common
            with chdir(common.parent):
                worktree_path = multi_params("--show-toplevel")
                worktree_path = Path(worktree_path).resolve() if worktree_path else None
            commits = multi_params("HEAD", "main", "master")
            commits = list(filter(lambda x: x, list(commits)))
            commit = commits[0] if commits else ""
            branch = _run_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            repo = worktree_path or repository_path
            if repo in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[repo]
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            elif worktree_path in XGIT_WORKTREES:
                worktree = XGIT_WORKTREES[worktree_path]
                xgit = _GitContext(
                    worktree=worktree,
                    path=Path("."),
                    commit=_git_object(commit, 'commit'),
                    branch=branch,
                )
                XGIT_CONTEXTS[worktree_path] = xgit
                return xgit
            elif repository_path in XGIT_REPOSITORIES:
                if repository_path in XGIT_REPOSITORIES:
                    repository = XGIT_REPOSITORIES[repository_path]
                else:
                    repository = _GitRepository(path=common)
                    XGIT_REPOSITORIES[repository_path] = repository
                if worktree_path is None:
                    return None
                worktree = _GitWorktree(
                    path=worktree_path,
                    repository=repository,
                    repository_path=repository_path,
                    branch=_GitRef(branch),
                    commit=_git_object(commit, 'commit'),
                    locked='',
                    prunable='',
                )
                XGIT_WORKTREES[worktree_path] = worktree
                xgit = _GitContext(
                    worktree=worktree,
                    path=Path("."),
                    commit=_git_object(commit, 'commit'),
                    branch=branch,
                )
                XGIT_CONTEXTS[worktree_path] = xgit
                return xgit
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

