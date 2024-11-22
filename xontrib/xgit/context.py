'''
Implementation of the `GitContext` class and related types.

* `GitContext` - a class that represents the context of our exploration
    of a git repository or worktree.
* `GitRepository` - a class that represents a git repository.
* `GitWorktree` - a class that represents a git worktree.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from dataclasses import dataclass
from typing import (
    MutableMapping, Optional, Sequence, cast, overload
)
from pathlib import Path, PurePosixPath
import sys

from xonsh.tools import chdir
from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import ContextKey
import xontrib.xgit.ref_types as rt
import xontrib.xgit.object_types as ot
from xontrib.xgit.to_json import JsonDescriber
from xontrib.xgit.entry_types import GitEntryTree
from xontrib.xgit.context_types import (
    GitContext,
    GitRepository,
    GitWorktree
)
import xontrib.xgit.objects as obj
import xontrib.xgit.repository as rr
import xontrib.xgit.worktree as wt
from xontrib.xgit.vars import (
    XGIT_CONTEXTS, XSH, XGIT_REPOSITORIES, XGIT_WORKTREES,
)
from xontrib.xgit.procs import _run_stdout
from xontrib.xgit.ref import _GitRef

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
        if self.__branch is None:
            return self.worktree.branch
        return self.__branch
    @branch.setter
    def branch(self, value: 'str|rt.GitRef|None'):
        match value:
            case None:
                self.__branch = None
            case rt.GitRef():
                self.__branch = value
            case str():
                value = value.strip()
                if value:
                    self.__branch = self.repository.get_reference(value,)
                else:
                    self.__branch = None
            case _:
                raise ValueError(f"Invalid branch: {value!r}")
    __commit: 'ot.GitCommit|None' = None
    @property
    def commit(self) -> ot.GitCommit:
        if self.__commit is None:
            return self.worktree.commit
        return self.__commit

    @commit.setter
    def commit(self, value: 'ot.Commitish'):
        match value:
            case None:
                self.__commit = None
            case str():
                value = value.strip()
                if value == '':
                    self.__commit = None
                    return
                self.__commit = self.repository.get_object(value, 'commit')
            case ot.GitCommit():
                self.__commit = value
            case ot.GitTagObject():
                # recurse if necessary to get the commit
                # or error if the tag doesn't point to a commit
                self.__commit = cast(ot.GitCommit, value.object)
            case rt.GitRef():
                self.__commit = cast(ot.GitCommit, value.target)
            case _:
                raise ValueError(f'Not a commit: {value}')

    @property
    def root(self) -> GitEntryTree:
        """
        Get the root tree entry.
        """
        tree= self.repository.get_object(self.commit.tree.hash, 'tree')
        name, entry = obj._git_entry(tree, "", "040000", "tree", "-",
                                 repository=self.worktree.repository,
                                 parent=self.commit,
                                 path=PurePosixPath("."))
        return entry


    def __init__(self, *args,
                 worktree: GitWorktree,
                 path: PurePosixPath = PurePosixPath("."),
                 branch: 'rt.RefSpec|None' = None,
                 commit: Optional['ot.Commitish'] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.__worktree = worktree
        self.__path = path
        self.branch = self.repository.get_reference(branch)
        if commit is None:
            commit = self.branch
        if commit is not None:
            self.commit = self.repository.get_object(commit, 'commit')

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
        commit: Optional['str|ot.GitCommit'] = None,
    ) -> "_GitContext":
        worktree = worktree or self.worktree
        path = path or self.__path
        branch = branch if branch is not None else self.branch
        if isinstance(commit, str):
            commit = self.repository.get_object(commit, 'commit')
        commit = commit or self.commit
        if isinstance(branch, str):
            if branch == '':
                branch = None
            else:
                branch = self.repository.get_reference(branch)
        return _GitContext(
            worktree=worktree,
            path=path,
            branch=cast('rt.RefSpec', branch),
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

def branch_and_commit(worktree: 'wt.GitWorktree') -> tuple['rt.GitRef|None', 'ot.GitCommit']:
    """
    Get the current branch and commit based on a worktree.
    """
    repository = worktree.repository
    branch_name = repository.git("symbolic-ref", "--quiet", 'HEAD', check=False)
    if branch_name:
        branch = repository.get_reference(branch_name)
    else:
        branch = None # Detached HEAD

    commit = multi_params("HEAD")
    if commit:
        commit = repository.get_object(commit, 'commit')
    else:
        raise ValueError("No commit found")
    return branch, commit

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
            repository = XGIT_REPOSITORIES.get(repository_path)
            if repository is None:
                repository = rr._GitRepository(path=common)
                XGIT_REPOSITORIES[repository_path] = repository
            worktree = XGIT_WORKTREES.get(worktree_path)
            if worktree is None:
                worktree: GitWorktree|None = repository.get_worktree(worktree_path)
            if worktree is None:
                worktree = wt._GitWorktree(
                    path=worktree_path,
                    repository=repository,
                    repository_path=repository_path,
                    branch=None,
                    commit=repository.get_object(commit, 'commit'),
                    locked='',
                    prunable='',
                )
                branch, commit = branch_and_commit(worktree)
                worktree.branch = branch
                worktree.commit = commit
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
                xgit = _GitContext(
                    worktree=worktree,
                    path=path,
                    commit=commit,
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
                repository = rr._GitRepository(path=common)
                XGIT_REPOSITORIES[repository_path] = repository
            with chdir(common.parent):
                worktree_path = multi_params("--show-toplevel")
                worktree_path = Path(worktree_path).resolve() if worktree_path else None
            commits = multi_params("HEAD", "main", "master" "origin/main", "origin/master", "origin/HEAD")
            commits = list(filter(lambda x: x, list(commits)))
            commit = commits[0] if commits else ""
            branch = repository.git("symbolic-ref", "--quiet", 'HEAD', check=False)
            repo = worktree_path or repository_path
            if repo in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[repo]
                xgit.commit = commit
                xgit.branch = branch
            if branch and '/' not in branch:
                raise ValueError(f"Invalid branch name from symbolic-ref, part 2: {branch!r}")
            elif worktree_path in XGIT_WORKTREES:
                worktree = XGIT_WORKTREES[worktree_path]
                xgit = _GitContext(
                    worktree=worktree,
                    path=PurePosixPath("."),
                    commit=worktree.repository.get_object(commit, 'commit'),
                    branch=branch,
                )
                XGIT_CONTEXTS[worktree_path] = xgit
                return xgit
            elif worktree_path is None:
                return None
            else:
                worktree = wt._GitWorktree(
                    path=worktree_path,
                    repository=repository,
                    repository_path=repository_path,
                    branch=_GitRef(branch, repository=repository),
                    commit=repository.get_object(commit, 'commit'),
                    locked='',
                    prunable='',
                )
                XGIT_WORKTREES[worktree_path] = worktree
                xgit = _GitContext(
                    worktree=worktree,
                    path=PurePosixPath("."),
                    commit=repository.get_object(commit, 'commit'),
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

