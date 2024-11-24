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
from types import MappingProxyType
from typing import (
    Mapping, Optional, cast
)
from pathlib import Path, PurePosixPath

from xonsh.built_ins import XonshSession
from xonsh.tools import chdir
from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.git_cmd import _GitCmd
from xontrib.xgit.person import Person
from xontrib.xgit.types import (
    GitHash, GitObjectReference, CleanupAction,
    GitNoRepositoryException, GitNoWorktreeException, GitException, GitError,
    GitDirNotFoundError, WorktreeNotFoundError, RepositoryNotFoundError,
    GitNoBranchException, GitValueError,
    GitRepositoryId, GitReferenceType,
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

    __repositories: dict[Path, GitRepository]
    def repositories(self) -> dict[Path, GitRepository]:
        return self.__repositories

    def open_repository(self, path: Path|str|GitRepository, /, *,
                        select: bool=True) -> GitRepository:
        """
        Open a repository at the given path. If the path is already open,
        return the existing repository.
        """
        if isinstance(path, GitRepository):
            repository = path
        else:
            path = Path(path)
            repository = self.__repositories.get(path)
            if repository is None:
                repository = rr._GitRepository(path=path,
                                            context=self,
                                            )
                self.__repositories[path] = repository
        if select and (self.__repository is not repository):
            self.repository = repository
        return repository


    def open_worktree(self, location: Path|str, /, *,
                    repository: Optional[GitRepository|str|Path]=None,
                    branch: Optional['PurePosixPath|str|rt.GitRef']=None,
                    commit: Optional['ot.Commitish']=None,
                    path: PurePosixPath=PurePosixPath(),
                    select: bool=True
                    ) -> 'GitWorktree':
        '''
        Open a worktree associated with this repository.
        '''
        location = Path(location).resolve()
        worktree = self.worktrees.get(location)
        if worktree is not None:
            return worktree
        if not location.is_dir():
            raise WorktreeNotFoundError(location)
        match repository:
            case GitRepository():
                pass
            case str() | Path():
                repository = self.open_repository(repository)
            case None:
                repo_path = location / '.git'
                if repo_path.exists():
                    repository = self.open_repository(repo_path)
                else:
                    raise RepositoryNotFoundError(location)
            case _:
                raise ValueError(f"Invalid repository: {repository}")
        if commit is None:
            head = self.rev_parse('HEAD')
            commit = repository.get_object(head, 'commit')
        if branch is None:
            branch_name = self.symbolic_ref('HEAD')
            if branch_name is not None:
                branch = repository.get_ref(branch_name)
        else:
            branch = repository.get_ref(branch)
        worktree = wt._GitWorktree(
            location=location,
            repository=repository,
            repository_path=repository.path,
            branch=branch,
            commit=commit,
            path=path,
            locked='',
            prunable='',
        )
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        self.__worktrees[location] = worktree
        repository._add_worktree(worktree)
        if select:
            self.worktree = worktree
        return worktree

    __worktrees: dict[Path, GitWorktree]
    @property
    def worktrees(self) -> Mapping[Path, GitWorktree]:
        return MappingProxyType(self.__worktrees)

    __worktree: GitWorktree|None
    @property
    def worktree(self) -> GitWorktree:
        if self.__worktree is None:
            raise ValueError("Worktree has not been set")
        return self.__worktree
    @worktree.setter
    def worktree(self, value: GitWorktree):
        self.__worktree = value
        self.__repository = value.repository

    __repository: GitRepository|None
    # Set for bare repositories; otherwise we use the one from
    # the current worktree.
    @property
    def repository(self) -> GitRepository:
        if self.__repository is None:
            raise GitNoRepositoryException()

        return self.__repository
    @repository.setter
    def repository(self, value: GitRepository):
        if value != self.__repository:
            self.__worktree = None
            self.__branch = None
            self.__commit = None
            self.__path = PurePosixPath()
        self.__repository = value

    __path: PurePosixPath
    @property
    def path(self) -> PurePosixPath:
        return self.__path

    @path.setter
    def path(self, value: PurePosixPath|str):
        self.__path = PurePosixPath(value)

    __branch: 'rt.GitRef|None'
    @property
    def branch(self) -> 'rt.GitRef':
        if self.__branch is None:
            if self.__worktree is None:
                raise GitNoBranchException()
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
                raise GitValueError(f"Invalid branch: {value!r}")

    __commit: 'ot.GitCommit|None'
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

    __objects: dict[GitHash, 'ot.GitObject']
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

    __people: dict[str, Person]
    @property
    def people(self) -> dict[str, Person]:
        return self.__people

    __object_references: defaultdict[GitHash, set[GitObjectReference]]
    @property
    def object_references(self) -> Mapping[GitHash, set[GitObjectReference]]:
        return MappingProxyType(self.__object_references)

    def add_reference(self, target: GitHash, repo: GitRepositoryId, ref: GitHash|PurePosixPath, t: GitReferenceType, /) -> None:
        self.__object_references[target].add((repo, ref, t))


    def __init__(self, session: XonshSession, /, *,
                 worktree: Optional[GitWorktree] = None,
                 branch: Optional['str|rt.GitRef'] = None,
                 commit: Optional['ot.Commitish'] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.__session = session
        self.__worktree = worktree
        self.__path = PurePosixPath()
        self.__repositories = {}
        self.__worktrees = {}
        self.__objects = {}
        if worktree is None:
            self.__repository = None
        else:
            self.__repository = worktree.repository
        self.branch = branch
        if commit is None:
            b = self.__branch
            if b is not None:
                t = b.target
                if t is not None:
                    commit = t.as_('commit')
        if commit is not None:
            self.commit = self.repository.get_object(commit, 'commit')
        self.branch = branch
        self.__people = dict()
        self.__object_references = defaultdict(set)


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
                wt = _relative_to_home(self.worktree.location)
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
        branch_name = repository.symbolic_ref('HEAD')
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

    __unload_actions: list[CleanupAction]
    def add_unload_action(self, action: CleanupAction):
        self.__unload_actions.append(action)

    def _do_unload_actions(self):
        """
        Unload a value supplied by the xontrib.
        """
        while len(self.__unload_actions) > 0:
            try:
                action = self.__unload_actions.pop()
                action()
            except Exception:
                from traceback import print_exc
                print_exc()

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