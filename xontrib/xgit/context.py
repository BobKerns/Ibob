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
from collections.abc import Mapping
from types import MappingProxyType
from typing import (
    Optional, cast
)
from pathlib import Path, PurePosixPath
from contextlib import suppress

from xonsh.built_ins import XonshSession
from xonsh.tools import chdir
from xonsh.lib.pretty import RepresentationPrinter
from xonsh.events import events

from xontrib.xgit.git_cmd import _GitCmd
from xontrib.xgit.person import Person
from xontrib.xgit.types import (
    ObjectId, CommitId, GitObjectReference,
    GitNoRepositoryException, GitNoWorktreeException,
    WorktreeNotFoundError, RepositoryNotFoundError,
    GitNoBranchException, GitValueError,
    GitRepositoryId, GitReferenceType,
    JsonData,
)
import xontrib.xgit.ref_types as rt
import xontrib.xgit.object_types as ot
from xontrib.xgit.views import JsonDescriber
from xontrib.xgit.entry_types import GitEntryTree
from xontrib.xgit.context_types import (
    GitContext,
    GitRepository,
    GitWorktree
)
import xontrib.xgit.repository as rr
import xontrib.xgit.worktree as wt
from xontrib.xgit.utils import path_and_parents, relative_to_home, shorten_branch

ROOT_REPO_PATH = PurePosixPath()

events.doc('on_xgit_repository_change', 'Runs when the current repository changes.')
events.doc('on_xgit_worktree_change', 'Runs when the current worktree changes.')
events.doc('on_xgit_branch_change', 'Runs when the current branch changes.')
events.doc('on_xgit_commit_change', 'Runs when the current commit changes.')
events.doc('on_xgit_path_change', 'Runs when the current path changes.')

class _GitContext(_GitCmd, GitContext):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    __session: XonshSession
    @property
    def session(self) -> XonshSession:
        '''
        Get the xonsh session this context is associated with.
        '''
        return self.__session

    __repositories: dict[Path, GitRepository]
    @property
    def repositories(self) -> dict[Path, GitRepository]:
        return self.__repositories

    def open_repository(self, path: Path|str|GitRepository, /, *,
                        select: bool=True) -> GitRepository:
        """
        Open a repository at the given path. If the path is already open,
        return the existing repository.

        If the path is a repository, return the repository. If the path
        is a worktree, return the repository associated with the worktree.

        Raises `RepositoryNotFoundError` if the repository is not found.

        PARAMETERS
        ----------
        path: Path | str | GitRepository
            The path to the repository, or the repository itself.
        select: bool
            If `True`, select the repository as the current repository.
        """
        if isinstance(path, GitRepository):
            repository = path
        else:
            path = Path(path)
            repository = self.__repositories.get(path)
            if repository is None:
                path, _ = self.find_repository(path)
                repository = rr._GitRepository(path=path,
                                            context=self,
                                            )
                self.__repositories[path] = repository
        if select and (self.__repository is not repository):
            events.on_xgit_repository_change.fire(old=self.__repository, new=repository)
            self.__repository = repository
            if (
                self.__worktree is not None
                and self.__worktree.repository is not repository
            ):
                self.worktree = None
        return repository


    def find_repository(self, path: Path, /) -> tuple[Path, Path|None]:
        '''
        Find the repository associated with the given path.

        Raises `RepositoryNotFoundError` if the repository is not found.

        This is done by looking for a .git directory in the path or
        any of its parents.

        PARAMETERS
        ----------
        path: Path
            The path to start looking for the repository.
        RETURNS
        -------
        common: Path
            The path to the main repository.
        private: Path | None
            The path to the private area for the worktree, or `None` if
            the repository is a bare repository.
        '''
        path = Path(path).resolve()
        for loc in path_and_parents(path):
            if loc.is_dir():
                if loc.name == '.git' and (loc / 'HEAD').exists():
                    return loc, loc.parent
                if loc.suffix == '.git':
                    return loc, None
            if (gitpath := (loc / '.git')).exists():
                return self._read_gitdir(gitpath)
        raise RepositoryNotFoundError(path)


    def _read_gitdir(self, gitdir: Path, /) -> tuple[Path, Path]:
        '''
        Read the .git file and return the path to the repository.

        Raises `RepositoryNotFoundError` if the repository is not found
        or is not a repository.

        PARAMETERS
        ----------
        gitdir: Path
            The path to the .git directory/file.
        RETURNS
        -------
        common: Path
            The path to the main repository.
        private: Path
            The path to the private area for the worktree.
        '''
        if gitdir.name == '.git':
            if gitdir.is_dir():
                if (gitdir / 'HEAD').exists():
                    return gitdir, gitdir
            elif gitdir.is_file():
                with gitdir.open() as f:
                    line = f.readline().strip()
                    if line.startswith('gitdir: '):
                        for_worktree = (gitdir.parent / line[8:])
                        return for_worktree.parent.parent, for_worktree
        raise RepositoryNotFoundError(gitdir)


    def find_worktree(self, path: Path, /) -> tuple[Path, Path, Path]:
        '''
        Find the worktree associated with the given path.

        Raises `WorktreeNotFoundError` if the worktree is not found.

        This is done by looking for a .git directory in the path or
        any of its parents.

        Raises `WorktreeNotFoundError` if the worktree is not found.

        PARAMETERS
        ----------
        path: Path

        RETURNS
        -------
        worktree: Path
            The path to the workktree
        common: Path
            The path to the shared repository
        private: Path
            The path to the private area for the worktree.
        '''
        path = Path(path).resolve()
        for p in path_and_parents(path):
            if p.suffix == ".git":
                # This is a repository, not a worktree
                raise WorktreeNotFoundError(path)
            if p.name == ".git":
                # This is a repository, inside a worktree
                return p.parent, p, p
            if (gitpath := (p / ".git")).is_dir():
                # This is a worktree, with a repository inside
                return p, gitpath, gitpath
            if gitpath.is_file():
                # This is a worktree, with a linked repository
                repo, private = self._read_gitdir(gitpath)
                return p, repo, private
        raise WorktreeNotFoundError(path)

    def open_worktree(self, location: Path|str, /, *,
                    repository: Optional[GitRepository|str|Path]=None,
                    branch: Optional['PurePosixPath|str|rt.GitRef']=None,
                    commit: Optional['ot.Commitish']=None,
                    path: Optional[PurePosixPath]=None,
                    select: bool=True
                    ) -> 'GitWorktree':
        '''
        Open a worktree associated with this repository.

        If the worktree is already open, return the existing worktree.

        If the location is not a directory, raise a `WorktreeNotFoundError`.

        If the repository is not provided, the repository is found by
        looking for a .git directory. If the repository is not found,
        raise a `RepositoryNotFoundError`.

        PARAMETERS
        ----------
        location: Path | str
            The path to the worktree.
        repository: GitRepository | Path | str | None
            The repository associated with the worktree. If not provided,
            the repository is found by looking for a .git directory.
        branch: str | GitRef | None
            The branch to use for the worktree. If not provided, the
            branch is found from the repository.
        commit: Commitish | None
            The commit to use for the worktree. If not provided, the
            commit is found from the repository.
        path: PurePosixPath
            The path within the worktree to use.
        select: bool
            If `True`, select the worktree as the current worktree.
        '''
        given_location = Path(location)
        location, _, _ = self.find_worktree(Path(location))
        for repo in self.repositories.values():
            if (wtree := repo.worktrees.get(location)) is not None:
                if select:
                    self.worktree = wtree
                return wtree
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
            case _ if hasattr(repository, 'get_object'):
                pass
            case _:
                raise GitValueError(f"Invalid repository: {repository}")
        if commit is None:
            head = self.rev_parse('HEAD')
            commit = repository.get_object(head, 'commit')
        if branch is None:
            branch_name = self.symbolic_ref('HEAD')
            if branch_name is not None:
                branch = repository.get_ref(branch_name)
        else:
            branch = repository.get_ref(branch)
        if path is None:
            p = given_location.relative_to(location)
            path = PurePosixPath(p)

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

        # If our table of worktrees is deferred, undefer it now.
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        self.__worktrees[location] = worktree

        # Make sure the repository knows about this worktree. (They can
        # become disconnected if moved.)
        repository._add_worktree(worktree)
        if select and self.__worktree is not worktree:
            events.on_xgit_worktree_change.fire(old=self.__worktree, new=worktree)
            self.__worktree = worktree
            self.path = worktree.path
            with suppress(GitNoBranchException):
                self.branch = worktree.branch
            self.commit = worktree.commit
        return worktree


    __worktree: GitWorktree|None
    @property
    def worktree(self) -> GitWorktree:
        '''
        Get/Set/Unset the current worktree.

        If the worktree is not set, raise a `GitNoWorktreeException`.
        '''
        if self.__worktree is None:
            raise GitNoWorktreeException("Worktree has not been set")
        return self.__worktree

    @worktree.setter
    def worktree(self, value: GitWorktree|None|str|Path):
        match value:
            case None:
                if self.__worktree is not None:
                    events.on_xgit_worktree_change.fire(old=self.__worktree, new=None)
                self.__worktree = None
                self.__path = PurePosixPath()
                self.branch = None
                self.commit = None
            case wt._GitWorktree():
                if self.__worktree is not value:
                    events.on_xgit_worktree_change.fire(old=self.__worktree, new=value)
                self.__worktree = value
                self.__path = value.path
                with suppress(GitNoBranchException):
                    self.branch = value.branch
                self.commit = value.commit
            case str() | Path():
                self.open_worktree(value)
            case _:
                raise GitValueError(f"estInvalid worktree: {value}")


    __repository: GitRepository|None
    # Set for bare repositories; otherwise we use the one from
    # the current worktree.
    @property
    def repository(self) -> GitRepository:
        '''
        Get/set the current repository.
        '''
        if self.__repository is None:
            raise GitNoRepositoryException()

        return self.__repository

    @repository.setter
    def repository(self, value: GitRepository|None|str|Path):
        match value:
            case None | GitRepository():
                if self.__repository is not value:
                    events.on_xgit_repository_change.fire(old=self.__repository,
                                                          new=value)
                self.__repository = None
                self.worktree = None
            case str() | Path():
                self.open_repository(value)
            case _:
                raise GitValueError(f"Invalid repository: {value}")


    __path: PurePosixPath
    @property
    def path(self) -> PurePosixPath:
        return self.__path

    @path.setter
    def path(self, value: PurePosixPath|str):
        value = PurePosixPath(value)
        if self.__path != value:
            self.__path = value
            events.on_xgit_path_change.fire(old=self.__path, new=value)


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
                branch = None
            case rt.GitRef():
                branch = value
            case str():
                value = value.strip()
                branch = self.repository.get_ref(value) if value else None
            case _:
                raise GitValueError(f"Invalid branch: {value!r}")
        if branch is not self.__branch:
            events.on_xgit_branch_change.fire(old=self.__branch, new=branch)
            self.__branch = branch


    __commit: 'ot.GitCommit|None'
    @property
    def commit(self) -> ot.GitCommit:
        if self.__commit is None:
            self.commit = self.worktree.commit
        if self.__commit is None:
            raise GitValueError("Commit has not been set.")
        return self.__commit

    @commit.setter
    def commit(self, value: 'ot.Commitish|None'):
        match value:
            case None:
                commit = None
            case str(v):
                value = CommitId(ObjectId(v.strip()))
                commit = self.repository.get_object(value, 'commit') if value else None
            case ot.GitCommit():
                commit = value
            case ot.GitTagObject():
                # recurse if necessary to get the commit
                # or error if the tag doesn't point to a commit
                commit = cast(ot.GitCommit, value.object)
            case rt.GitRef():
                commit = cast(ot.GitCommit, value.target)
            case _:
                raise GitValueError(f'Not a commit: {value}')
        if commit is not self.__commit:
            events.on_xgit_commit_change.fire(old=self.__commit, new=commit)
            self.__commit = commit

    __objects: dict[ObjectId, 'ot.GitObject']
    @property
    def objects(self) -> Mapping[ObjectId, 'ot.GitObject']:
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

    __object_references: defaultdict[ObjectId, set[GitObjectReference]]
    @property
    def object_references(self) -> Mapping[ObjectId, set[GitObjectReference]]:
        return MappingProxyType(self.__object_references)

    def add_reference(self,
                      target: ObjectId,
                      repo: GitRepositoryId,
                      ref: ObjectId|PurePosixPath,
                      t: GitReferenceType,
                      /) -> None:
        obj_ref = cast(GitObjectReference, (repo, ref, t))
        self.__object_references[target].add(obj_ref)

    __worktrees: dict[Path, GitWorktree]

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
        self.__branch = None
        self.__commit = None
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
        else:
            self.commit = None
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
        def bname(obj):
            with suppress(GitNoBranchException):
                return shorten_branch(obj.branch.name)
            return '(None)'

        if cycle:
            p.text(f"GitContext({self.worktree} {self.path}")
        else:
            with p.group(4, "$XGIT (context)"):
                p.break_()
                with p.group(2, '$XGIT.repository:'):
                    try:
                        repo = self.repository
                        p.break_()
                        p.pretty(repo)
                    except GitNoRepositoryException:
                        p.text("Repository: Not set")
                        return
                    except Exception as e:
                        p.text(f"Error: {e}")
                        return
                p.break_()
                with p.group(2, '$XGIT.worktree:'):
                    try:
                        p.break_()
                        wt = self.worktree
                        wt_loc = relative_to_home(wt.location)
                        p.text(f".location: {wt_loc}")
                        if wt.repository_path != wt.repository.path:
                            with p.group(2):
                                p.break_()
                                pth = relative_to_home(wt.repository_path)
                                p.text(f".repository_path (private): {pth}")
                                p.break_()
                                pth = relative_to_home(wt.repository.path)
                                p.text(f".repository.path (shared): {pth}")
                        p.break_()
                        p.text(f".branch: {bname(wt)}")
                        p.break_()
                        p.text(f".commit: {wt.commit.hash[:14]}")
                    except GitNoWorktreeException:
                        p.break_()
                        p.text("Worktree: Not set")
                    except Exception as e:
                        p.text(f"Error: {e}")
                        return
                p.breakable()
                with p.group(2, '$XGIT:'):
                    p.break_()
                    p.text(f".path: {self.path}")
                    p.break_()
                    p.text(f".branch: {bname(self)}")
                    p.break_()
                    p.text(f".commit: {self.commit.hash[:14]}")
                    with p.group(2):
                        p.break_()
                        p.text(f'{self.commit.author.person.name} '
                               f'{self.commit.author.date}')
                        for line in self.commit.message.splitlines():
                            p.break_()
                            p.text(line)
                p.break_()
                p.text(f"cwd: {relative_to_home(Path.cwd())}")

    def to_json(self, describer: JsonDescriber) -> JsonData:
        branch = self.branch.name if self.branch else None
        return cast(JsonData, {
            "worktree": describer.to_json(self.worktree),
            "path": str(self.path),
            "branch": branch,
            "commit": self.commit.hash,
        })

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

    def branch_and_commit(self,
                          worktree: 'wt.GitWorktree',
                          ) -> tuple['rt.GitRef|None', 'ot.GitCommit']:
        """
        Get the current branch and commit based on a worktree. These are nouns,
        not actions. No branches or commits are created.
        """
        repository = worktree.repository
        branch_name = repository.symbolic_ref('HEAD')
        branch = repository.get_ref(branch_name) if branch_name else None

        commit = self.rev_parse("HEAD")
        if commit:
            commit = repository.get_object(commit, 'commit')
        else:
            raise GitValueError("No commit found")
        return branch, commit