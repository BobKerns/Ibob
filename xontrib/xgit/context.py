'''
Implementation of the `GitContext` class and related types.

* `GitContext` - a class that represents the context of our exploration
    of a git repository or worktree.
* `GitRepository` - a class that represents a git repository.
* `GitWorktree` - a class that represents a git worktree.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from contextlib import suppress
from dataclasses import dataclass, field
from tabnanny import check
from textwrap import shorten
from typing import (
    MutableMapping, Optional, Sequence, TypeAlias, cast, overload
)
from pathlib import Path, PurePosixPath
import sys
import shutil
from subprocess import run, Popen, PIPE

from xonsh.tools import chdir
from xonsh.lib.pretty import RepresentationPrinter

import xontrib.xgit.ref as xr
import xontrib.xgit.ref_types as rt
from xontrib.xgit.to_json import JsonDescriber
from xontrib.xgit.types import ContextKey, InitFn, GitHash
from xontrib.xgit.entry_types import GitEntryTree
from xontrib.xgit.object_types import GitObject, GitTagObject, GitCommit
from xontrib.xgit.context_types import (
    GitCmd,
    GitContext,
    GitRepository,
    GitWorktree
)
from xontrib.xgit.objects import _git_object, _git_entry
from xontrib.xgit.vars import (
    XGIT_CONTEXTS, XSH, XGIT_REPOSITORIES, XGIT_WORKTREES,
)
from xontrib.xgit.procs import _run_stdout
from xontrib.xgit.objects import _git_object
from xontrib.xgit.ref import _GitRef

DEFAULT_BRANCH="HEAD"

WorktreeMap: TypeAlias = dict[Path, GitWorktree]

class _GitCmd(GitCmd):
    """
    A context for a git command.
    """
    __path: Path
    __git: Path
    def __get_path(self, path: Path|str|None) -> Path:
        if path is None:
            return self.__path
        return (self.__path / path).resolve()
    def __init__(self, path: Path):
        self.__path = path.resolve()
        git = shutil.which("git")
        if git is None:
            raise ValueError("git command not found")
        self.__git = Path(git)
    def git(self, *args,
            path: Optional[str|Path]=None,
            check=True,
            **kwargs) -> str:
        return run([str(self.__git), *args],
            stdout=PIPE,
            text=True,
            check=check,
            cwd=self.__get_path(path),
            **kwargs).stdout.strip()
    def git_lines(self, *args,
            path: Optional[str|Path]=None,
            check=True,
            **kwargs) -> list[str]:
        return run([str(self.__git),*args],
            stdout=PIPE,
            text=True,
            check=check,
            cwd=self.__get_path(path),
            **kwargs).stdout.splitlines()
    def git_stream(self, *args,
                path: Optional[str|Path]=None,
                **kwargs):
        cmd = [str(a) for a in (self.__git, *args)]
        proc = Popen(cmd,
            stdout=PIPE,
            text=True,
            cwd=self.__get_path(path),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        for line in stream:
            yield line.rstrip()
        proc.wait()

    def git_binary(self, *args,
                   path: Optional[str|Path]=None,
                     **kwargs):

        cmd = [str(a) for a in (self.__git, *args)]
        proc = Popen(cmd,
            stdout=PIPE,
            text=False,
            cwd=self.__get_path(path),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        return stream

    @overload
    def rev_parse(self, params: str, /) -> str: ...
    @overload
    def rev_parse(self,param: str, *_params: str) -> Sequence[str]: ...
    def rev_parse(self, param: str, *params: str) -> Sequence[str] | str:
        """
        Use `git rev-parse` to get multiple parameters at once.
        """
        all_params = [param, *params]
        val = self.git_lines("rev-parse", *all_params)
        if val:
            return val
        else:
            # Try running them individually.
            result = [self.git("rev-parse", param) for param in all_params]
        if len(all_params) == 1:
            # Otherwise we have to assign like `value, = multi_params(...)`
            # The comma is` necessary to unpack the single value
            # but is confusing and easy to forget
            # (or not understand if you don't know the syntax).
            return result[0]
        return result


class _GitRepository(_GitCmd, GitRepository):
    """
    A git repository.
    """

    __path: Path
    @property
    def path(self) -> Path:
        """
        The path to the repository. If this is a worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `common`.
        """
        return self.__path

    __worktrees: WorktreeMap|InitFn['_GitRepository',WorktreeMap] = field(default_factory=dict)
    @property
    def worktrees(self) -> dict[Path, GitWorktree]:
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        return self.__worktrees

    __preferred_worktree: GitWorktree|None = None
    @property
    def worktree(self) -> GitWorktree:
        """
        Get the preferred worktree.
        """
        if self.__preferred_worktree is not None:
            return self.__preferred_worktree
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        if self.path.name == ".git":
            worktree = self.get_worktree(self.path.parent)
            if worktree is not None:
                self.__preferred_worktree = worktree
                return worktree
            commit = self.git('rev-parse', '--verify', '--quiet', 'HEAD', check=False)
            branch_name = self.git('symbolic-ref', '--quiet', 'HEAD', check=False)
            branch = None
            if branch_name:
                branch = _GitRef(branch_name, repository=self)
            worktree = _GitWorktree(
                            path=self.path.parent,
                            repository=self,
                            repository_path=self.path,
                            branch=branch,
                            commit=_git_object(commit, self, 'commit'),
                            locked='',
                            prunable='',
                        )
            self.__preferred_worktree = worktree
            self.__worktrees[self.path.parent] = worktree
            return cast(GitWorktree, worktree)

        with suppress(StopIteration):
            worktree = next(iter(self.worktrees.values()))
            if worktree is not None:
                self.__preferred_worktree = worktree
                return worktree
        raise ValueError("No worktrees found for repository")

    def get_worktree(self, key: Path|str) -> GitWorktree|None:
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        return self.__worktrees.get(Path(key).resolve())

    __objects: dict[GitHash, GitObject] = field(default_factory=dict)


    """
    The path to the common part of the repository. This is the same for all worktrees.
    """

    def __init__(self, *args,
                 path: Path = Path(".git"),
                 **kwargs):
        super().__init__(path)
        self.__path = path
        def init_worktrees(self: _GitRepository) -> WorktreeMap:
            bare: bool = False
            result: dict[Path,GitWorktree] = {}
            worktree: Path = path.parent.resolve()
            branch: 'rt.GitRef|None' = None
            commit: GitCommit|None = None
            locked: str = ''
            prunable: str = ''
            for l in self.git_lines('worktree', 'list', '--porcelain'):
                match l.strip().split(' ', maxsplit=1):
                    case ['worktree', wt]:
                        worktree = Path(wt).resolve()
                    case ['HEAD', c]:
                        commit = _git_object(c, self, 'commit')
                        self.__objects[commit.hash] = commit
                    case ['branch', b]:
                        b = b.strip()
                        if b:
                            branch = _GitRef(b, repository=self)
                        else:
                            branch = None
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
                    case _ if l.strip() == '':
                        repository_path = Path(self.git('rev-parse', '--absolute-git-dir'))
                        repository_path = repository_path.resolve()
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
        self.__worktrees = init_worktrees
        self.__objects = {}

    def to_json(self, describer: JsonDescriber):
        return str(self.path)

    @staticmethod
    def from_json(data: str, describer: JsonDescriber):
        return _GitRepository(data)

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
        if cycle:
            p.text(f"GitRepository({self.path}")
        else:
            with p.group(4, "Repository:"):
                p.break_()
                p.text(f"path: {_relative_to_home(self.path)}")
                p.break_()
                with p.group(4, "worktrees:", "\n"):
                    wts = self.worktrees.values()
                    f1 = max(len(str(_relative_to_home(wt.path)))
                             for wt in wts)
                    def shorten_branch(branch: str):
                        branch = branch.replace('refs/heads/', '')
                        branch = branch.replace('refs/remotes/', '')
                        branch = branch.replace('refs/tags/', 'tag:')
                        return branch
                    f2 = max(len(shorten_branch(wt.branch.name if wt.branch else '-')) for wt in wts)
                    f4 = max(len(wt.commit.author.person.name) for wt in wts)
                    for wt in self.worktrees.values():
                        p.breakable()
                        branch = shorten_branch(wt.branch.name if wt.branch else '-')
                        p.text(f"{str(_relative_to_home(wt.path)):{f1}s}: {branch:{f2}s} {wt.commit.hash} {wt.commit.author.person.name:{f4}s} {wt.commit.author.date}")
                p.breakable()
                p.text(f"preferred_worktree: {_relative_to_home(self.worktree.path)}")
                p.break_()
                p.text(f"objects: {len(self.__objects)}")

class _GitWorktree(_GitCmd, GitWorktree):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """
    __repository: GitRepository
    @property
    def repository(self) -> GitRepository:
        return self.__repository

    __repository_path: Path
    @property
    def repository_path(self) -> Path:
        """
        The path to the repository. If this is a separate worktree,
        it is the path to the worktree-specific part.
        For the main worktree, this is the same as `repository.path`.
        """
        return self.__repository_path

    __path: Path | None = Path(".")
    @property
    def path(self) -> Path | None:
        return self.__path

    __branch: 'rt.GitRef|None'
    @property
    def branch(self) -> 'rt.GitRef|None':
        return self.__branch
    @branch.setter
    def branch(self, value: 'rt.GitRef|str|None'):
        match value:
            case rt.GitRef():
                self.__branch = value
            case str():
                value = value.strip()
                if value:
                    self.__branch = _GitRef(value, repository=self.__repository)
                else:
                    self.__branch = None
            case None:
                self.__branch = None
            case _:
                raise ValueError(f"Invalid branch: {value!r}")
    __commit: GitCommit|None
    @property
    def commit(self) -> GitCommit:
        assert self.__commit is not None, "Commit has not been set."
        return self.__commit
    @commit.setter
    def commit(self, value: str|GitCommit):
        match value:
            case str():
                value = value.strip()
                hash = self.git('rev-parse', value)
                self.__commit = _git_object(hash, self.repository, 'commit')
            case GitCommit():
                self.__commit = value
            case _:
                raise ValueError(f'Not a commit: {value}')
    locked: str
    prunable: str

    def __init__(self, *args,
                repository: GitRepository,
                path: Path,
                repository_path: Path,
                branch: 'rt.GitRef|str|None',
                commit: GitCommit,
                locked: str = '',
                prunable: str = '',
                **kwargs
            ):
            super().__init__(path)
            self.__repository = repository
            self.__path = path
            self.__repository_path = repository_path
            self.branch = branch
            self.commit = commit
            self.locked = locked
            self.prunable = prunable

    def to_json(self, describer: JsonDescriber):
        branch = self.branch.name if self.branch else None
        return {
            "repository": str(self.repository.path),
            "repository_path": str(self.repository_path),
            "path": str(self.path),
            "branch": branch,
            "commit": self.commit.hash,
            "locked": self.locked,
            "prunable": self.prunable,
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        repository = _GitRepository(Path(data['repository']))
        return _GitWorktree(
            repository=repository,
            repository_path=Path(data["repository_path"]),
            path=Path(data["path"]),
            branch=_GitRef(data["branch"], repository=describer.repository),
            commit=_git_object(data["commit"], repository, 'commit'),
            locked=data["locked"],
            prunable=data["prunable"],
        )

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
        if cycle:
            p.text(f"GitWorktree({self.path}")
        else:
            with p.group(4, "Worktree:"):
                p.break_()
                p.text(f"repository: {self.repository.path}")
                p.break_()
                p.text(f"repository_path: {self.repository_path}")
                p.break_()
                p.text(f"path: {self.path}")
                p.break_()
                p.text(f"branch: {self.branch}")
                p.break_()
                p.text(f"commit: {self.commit.hash}")
                with p.group(2):
                    p.break_()
                    p.text(f'{self.commit.author} {self.commit.author.date}')
                    for line in self.commit.message.splitlines():
                        p.break_()
                        p.text(line)
                p.break_()
                p.text(f"locked: {self.locked}")
                p.break_()
                p.text(f"prunable: {self.prunable}")


@dataclass
class _GitContext(GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    __worktree: GitWorktree
    @property
    def worktree(self) -> GitWorktree:
        return self.__worktree

    @property
    def repository(self) -> GitRepository:
        return self.worktree.repository

    __path: PurePosixPath = PurePosixPath(".")
    @property
    def path(self) -> PurePosixPath:
        return self.__path

    @path.setter
    def path(self, value: PurePosixPath|str):
        self.__path = PurePosixPath(value)

    __branch: 'rt.GitRef|None' = None
    @property
    def branch(self) -> 'rt.GitRef|None':
        return self.__branch
    @branch.setter
    def branch(self, value: 'str|rt.GitRef|None'):
        match value:
            case rt.GitRef():
                self.__branch = value
            case str():
                value = value.strip()
                if value:
                    self.__branch = _GitRef(value, repository=self.worktree.repository)
                else:
                    self.__branch = None
            case None:
                self.__branch = None
            case _:
                raise ValueError(f"Invalid branch: {value!r}")
    __commit: GitCommit|None = None
    @property
    def commit(self) -> GitCommit:
        assert self.__commit is not None, "Commit has not been set."
        return self.__commit

    @commit.setter
    def commit(self, value: str|GitCommit|_GitRef|GitTagObject):
        match value:
            case str():
                value = value.strip()
                hash = self.worktree.git('rev-parse', value)
                self.__commit = _git_object(hash, self.worktree.repository, 'commit')
            case GitCommit():
                self.__commit = value
            case GitTagObject():
                # recurse if necessary to get the commit
                # or error if the tag doesn't point to a commit
                self.__commit = cast(GitCommit, value.object)
            case rt.GitRef():
                # recurse if necessary to get the commit
                # or error if the ref doesn't point to a commit
                self.__commit = cast(GitCommit, value.target)
            case _:
                raise ValueError(f'Not a commit: {value}')

    @property
    def root(self) -> GitEntryTree:
        """
        Get the root tree entry.
        """
        tree = _git_object(self.commit.tree.hash, self.worktree.repository, 'tree')
        name, entry = _git_entry(tree, "", "040000", "tree", "-",
                                 repository=self.worktree.repository,
                                 parent=self.commit,
                                 path=PurePosixPath("."))
        return entry

    def __init__(self, *args,
                 worktree: GitWorktree,
                 path: PurePosixPath = PurePosixPath("."),
                 branch: 'str|rt.GitRef|None' = DEFAULT_BRANCH,
                 commit: str|GitCommit = DEFAULT_BRANCH,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.__worktree = worktree
        self.commit = commit
        self.__path = path
        match branch:
            case str():
                branch = branch.strip()
                if branch:
                    self.branch = _GitRef(branch,
                                          repository=self.worktree.repository)
                else:
                    self.branch = None
            case rt.GitRef():
                self.branch = cast('rt.GitRef', branch)

    def reference(self, subpath: Optional[PurePosixPath | str] = None) -> ContextKey:
        subpath = PurePosixPath(subpath) if subpath else None
        key = self.worktree.path
        commit = self.commit
        hash = '''
        if commit is not None:
            hash = commit.hash
        '''
        branch_name = None
        if subpath is None:
            branch_name = self.branch.name if self.branch else None
            return (key, self.__path, branch_name, hash)
        return (key, subpath, branch_name, hash)

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
        path: Optional[PurePosixPath] = None,
        branch: Optional['str|rt.GitRef'] = None,
        commit: Optional[str|GitCommit] = None,
    ) -> "_GitContext":
        worktree = worktree or self.worktree
        path = path or self.__path
        branch = branch if branch is not None else self.branch
        if isinstance(commit, str):
            commit = _git_object(commit, worktree.repository, 'commit')
        commit = commit or self.commit
        if isinstance(branch, str):
            if branch == '':
                branch = None
            else:
                branch = _GitRef(branch, repository=worktree.repository)
        return _GitContext(
            worktree=worktree,
            path=path,
            branch=branch,
            commit=commit,
        )

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
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
                    p.text(f'{self.commit.author} {self.commit.author.date}')
                    for line in self.commit.message.splitlines():
                        p.break_()
                        p.text(line)
                p.break_()
                p.text(f"cwd: {_relative_to_home(Path.cwd())}")

    def to_json(self, describer: JsonDescriber):
        assert self.commit is not None, "Commit has not been set"
        branch = self.branch.name if self.branch else None
        return {
            "worktree": describer.to_json(self.worktree),
            "path": str(self.path),
            "branch": branch,
            "commit": self.commit.hash,
        }

    @staticmethod
    def from_json(data: dict, describer: JsonDescriber):
        repository = describer.repository
        return _GitContext(
            worktree=describer.from_json(data["worktree"], repository=repository),
            path=describer.from_json(data["git_path"], repository=repository),
            branch=describer.from_json(data["branch"], repository=repository),
            commit=describer.from_json(data["commit"], repository=repository),
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

    This run the command in the current working directory.
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
            worktree: GitWorktree|None = repository.get_worktree(worktree_path)
            if worktree is None:
                worktree = _GitWorktree(
                    path=worktree_path,
                    repository=repository,
                    repository_path=repository_path,
                    branch=None,
                    commit=_git_object(commit, repository, 'commit'),
                    locked='',
                    prunable='',
                )
                repository.worktrees[worktree_path] = worktree

            path = PurePosixPath(Path.cwd().relative_to(worktree_path))
            branch = repository.git("symbolic-ref", '--quiet', 'HEAD', check=False)
            if branch and '/' not in branch:
                raise ValueError(f"Invalid branch name from symbolic-ref: {branch!r}")
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
                        commit=_git_object(commit, repository, 'commit'),
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
                        branch=branch,
                        commit=_git_object(commit, repository, 'commit'),
                        locked='',
                        prunable='',
                    )
                    XGIT_WORKTREES[worktree_path] = worktree
                    gctx = _GitContext(
                        worktree=worktree,
                        path=path,
                        commit=_git_object(commit, repository, 'commit'),
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
                        branch=branch,
                        commit=_git_object(commit, repository, 'commit'),
                        locked='',
                        prunable='',
                    )
                    XGIT_WORKTREES[worktree_path] = worktree
                    xgit = _GitContext(
                        worktree=worktree,
                        path=path,
                        commit=_git_object(commit, repository, 'commit'),
                        branch=branch,
                    )
                    XGIT_CONTEXTS[key] = xgit
                    return xgit
        elif in_git == "true":
            # Inside a .git directory or bare repository.
            repository_path, common = multi_params("--absolute-git-dir", "--git-common-dir")
            repository_path = Path(repository_path).resolve()
            repository = XGIT_REPOSITORIES.get(repository_path)
            common = repository_path / common
            if repository is None:
                repository = _GitRepository(path=common)
                XGIT_REPOSITORIES[repository_path] = repository
            with chdir(common.parent):
                worktree_path = multi_params("--show-toplevel")
                worktree_path = Path(worktree_path).resolve() if worktree_path else None
            commits = multi_params("HEAD", "main", "master")
            commits = list(filter(lambda x: x, list(commits)))
            commit = commits[0] if commits else ""
            branch = repository.git("symbolic-ref", "--quiet", 'HEAD', check=False)
            if branch and '/' not in branch:
                raise ValueError(f"Invalid branch name from symbolic-ref, part 2: {branch!r}")
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
                    path=PurePosixPath("."),
                    commit=_git_object(commit, worktree.repository, 'commit'),
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
                    branch=_GitRef(branch, repository=repository),
                    commit=_git_object(commit, repository, 'commit'),
                    locked='',
                    prunable='',
                )
                XGIT_WORKTREES[worktree_path] = worktree
                xgit = _GitContext(
                    worktree=worktree,
                    path=PurePosixPath("."),
                    commit=_git_object(commit, repository, 'commit'),
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
        if env.get("XGIT_TRACE_ERRORS") or True:
            import traceback
            traceback.print_exc()
        print(f"Error setting git context: {ex}", file=sys.stderr)
    return None

