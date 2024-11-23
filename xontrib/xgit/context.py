'''
Implementation of the `GitContext` class and related types.

* `XonshSession` - on startup, we are provided with the xonsh session.
    This is used to access the environment and other session data.
    It is also used to register new aliases, history backends, and
    event listeners. On unload, we will use it to restore the environment
    to its previous state, and disable any further interaction. This
    will help ensure test isolation.
* `GitContext` - a class that represents the context of our exploration
    of git repositories and worktrees.
* `GitRepository` - A `GitContext` provides access to a `GitRepository`,
    which is the root of the git repository and everything related to it.
* `GitWorktree` - A `GitRepository` provides access to 0 or more
    `GitWorktree` instances that represents a git worktree.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from collections import defaultdict
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import (
    Callable, Mapping, Optional, cast
)
from pathlib import Path, PurePosixPath

from xonsh.built_ins import XonshSession
from xonsh.tools import chdir
from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.git_cmd import _GitCmd
from xontrib.xgit.person import Person
from xontrib.xgit.types import (
    GitHash, GitObjectReference,
    GitNoRepositoryException, GitNoWorktreeException, GitException, GitError,
    GitDirNotFoundError, WorktreeNotFoundError, RepositoryNotFoundError,
)
import xontrib.xgit.ref_types as rt
import xontrib.xgit.object_types as ot
from xontrib.xgit.to_json import JsonDescriber
from xontrib.xgit.entry_types import GitEntryTree
from xontrib.xgit.context_types import (
    GitContext,
    GitRepository,
    GitWorktree
)
import xontrib.xgit.repository as rr
import xontrib.xgit.worktree as wt

@dataclass
class _GitContext(_GitCmd, GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    __session: XonshSession
    @property
    def session(self) -> XonshSession:
        return self.__session

    __repositories: dict[Path, GitRepository] = field(default_factory=dict)
    def repositories(self) -> dict[Path, GitRepository]:
        return _GitContext.__repositories

    def open_repository(self, path: Path|str) -> GitRepository:
        path = Path(path)
        repository = _GitContext.__repositories.get(path)
        if repository is None:
            repository = rr._GitRepository(path=path)
            _GitContext.__repositories[path] = repository
        return repository

    __worktrees: dict[Path, GitWorktree] = field(default_factory=dict)
    @property
    def worktrees(self) -> Mapping[Path, GitWorktree]:
        return MappingProxyType(self.__worktrees)

    __worktree: GitWorktree|None = None
    @property
    def worktree(self) -> GitWorktree:
        raise ValueError("Worktree has not been set")
        return self.__worktree
    @worktree.setter
    def worktree(self, value: GitWorktree):
        self.__worktree = value
        self.__repository = value.repository

    __repository: GitRepository|None = None
    # Set for bare repositories; otherwise we use the one from
    # the current worktree.
    @property
    def repository(self) -> GitRepository:
        if self.__repository is None:
            raise GitNoRepositoryException()

        return self.__repository

    def open_worktree(self, path: 'Path|str|GitWorktree|GitRepository',
                      select: bool=True,
                      ) -> GitWorktree:
        match path:
            case GitWorktree():
                if select:
                    self.worktree = path
                return path
            case GitRepository():
                if select:
                    self.__repository = path
                worktree = path.worktree
                if select:
                    self.__worktree = worktree
                    return path.worktree
                return worktree
            case Path()|str():
                path = Path(path)
                worktree = _GitContext.__worktrees.get(path)
                if worktree is not None:
                    if select:
                        self.__worktree = worktree
                    return worktree
                root, private_repo, repo_path, commit_id = self.worktree_locations(path)
                worktree = _GitContext.__worktrees.get(path)
                if worktree is not None:
                    if select:
                        self.__worktree = worktree
                        self.__repository = worktree.repository
                    return worktree
                repository = self.open_repository(repo_path)
                commit = repository.get_object(commit_id, 'commit')
                worktree = wt._GitWorktree(
                    path=path,
                    repository=self.repository,
                    repository_path=repo_path,
                    branch=None,
                    commit=commit,
                    )
        path = Path(path)
        worktree = _GitContext.__worktrees.get(path)
        if worktree is None:
            worktree = repository.worktree
            _GitContext.__worktrees[path] = worktree
        self.__worktree = worktree
        return worktree

    __path: PurePosixPath = PurePosixPath()
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
                    self.__branch = self.repository.get_ref(value,)
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

    __objects: dict[GitHash, 'ot.GitObject'] =  field(default_factory=dict)
    @property
    def objects(self) -> Mapping[GitHash, 'ot.GitObject']:
        return MappingProxyType(self.__objects)

    @property
    def root(self) -> GitEntryTree:
        """
        Get the root tree entry.
        """
        tree= self.repository.get_object(self.commit.tree.hash, 'tree')
        name, entry = tree._git_entry(tree, "", "040000", "tree", -1,
                                 repository=self.worktree.repository,
                                 parent=self.commit,
                                 path=PurePosixPath("."))
        return entry

    __people: dict[str, Person] = field(default_factory=dict)
    @property
    def people(self) -> set[Person]:
        return set(self.__people.values())

    __object_references: defaultdict[GitHash, set[GitObjectReference]] = field(default_factory=lambda: defaultdict(set))
    @property
    def object_references(self) -> Mapping[GitHash, set[GitObjectReference]]:
        return MappingProxyType(self.__object_references)

    def add_reference(self, hash: GitHash, reference: GitObjectReference) -> None:
        self.__object_references[hash].add(reference)

    def __init__(self, session: XonshSession, /,
                 worktree: Optional[GitWorktree] = None,
                 branch: Optional['str|rt.GitRef'] = None,
                 commit: Optional['str|ot.GitCommit'] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.__worktree = worktree
        self.__path = PurePosixPath()
        self.branch = branch
        if commit is None:
            b = self.branch
            if b is not None:
                t = b.target
                if t is not None:
                    commit = t.as_('commit')
        if commit is not None:
            self.commit = self.repository.get_object(commit, 'commit')

    @property
    def cwd(self) -> Path:
        return Path.cwd()
    @cwd.setter
    def cwd(self, value: Path|str):
        chdir(Path(value))

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
        context = repository.context
        context.open_repository(data["worktree"]["repository"])
        context.open_worktree(data["worktree"]["path"])
        context.branch = describer.from_json(data["branch"], repository=repository)
        context.commit = describer.from_json(data["commit"], repository=repository)
        context.path = PurePosixPath(data["path"])

        repository = describer.repository

    def branch_and_commit(self, worktree: 'wt.GitWorktree') -> tuple['rt.GitRef|None', 'ot.GitCommit']:
        """
        Get the current branch and commit based on a worktree. These are nouns,
        not actions. No branches or commits are created.
        """
        repository = worktree.repository
        branch_name = repository.git("symbolic-ref", "--quiet", 'HEAD', check=False)
        if branch_name:
            branch = repository.get_ref(branch_name)
        else:
            branch = None # Detached HEAD

        commit = self.rev_parse("HEAD")
        if commit:
            commit = repository.get_object(commit, 'commit')
        else:
            raise ValueError("No commit found")
        return branch, commit

    ___unload_actions: list[Callable[[], None]] = field(default_factory=list)


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