'''
Types pertaining to the context of a git repository and our operations on it.

The key types are:
- `GitWorktree`: The root directory of where the files are checked out.
- `GitRepository`: The common part of the repository. This is the same for all
    worktrees associated with a repository.
- `GitContext`: The context for git commands.
    This includes the worktree and its repository, but also the current branch,
    commit, and path within the worktree/GitTree that we are exploring.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''

from abc import abstractmethod
from pathlib import Path, PurePosixPath
from collections.abc import Mapping
from typing import (
    Literal, Protocol, overload, runtime_checkable, Optional,
    TypeAlias, TYPE_CHECKING, cast,
)

from xonsh.built_ins import XonshSession

from xontrib.xgit.types import (
    GitObjectReference, GitObjectType, GitException,
    ObjectId, GitRepositoryId, GitReferenceType,
)
from xontrib.xgit.views.json_types import Jsonable
import xontrib.xgit.person as people
import xontrib.xgit.git_cmd as gc
import xontrib.xgit.object_types as ot
import xontrib.xgit.ref_types as rt
if TYPE_CHECKING:
    from xontrib.xgit.context_types import GitWorktree

WorktreeMap: TypeAlias = dict[Path, 'GitWorktree']


@runtime_checkable
class GitRepository(Jsonable, gc.GitCmd, Protocol):
    """
    A git repository.

    This is the repository, not a worktree (`GitWorktree`).
    This includes the worktree that is the parent of thee
    `.git` directory. That is a worktree with a repository
    inside it.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """
        A semi-unique identifier for the repository.

        Repositories which are clones of each other will have the same id.
        This is the xor of the hashes of repository's root commits.

        Repositories which have the same `id` will have some history in common.
        New branches can be pushed and pulled between them.
        """
        ...

    @property
    @abstractmethod
    def context(self) -> 'GitContext':
        '''
        The context for git commands.
        '''
        ...

    @property
    @abstractmethod
    def path(self) -> Path:
        """
        The path to the common part of the repository. This is the same for all
        worktrees associated with a repository.
        """
        ...


    @property
    @abstractmethod
    def worktree(self) -> 'GitWorktree':
        '''
        The main worktree associated with this repository.

        This is used by default for some operation which require a worktree.
        '''
        ...

    @property
    @abstractmethod
    def worktrees(self) -> Mapping[Path, 'GitWorktree']:
        '''
        Worktrees known to be associated with this repository.
        '''
        ...

    @abstractmethod
    def get_worktree(self, key: Path|str) -> 'GitWorktree|None':
        '''
        Get a worktree by its path. Canonicalizes the path first,
        making this the preferred way to get a worktree.
        '''
        ...

    @overload
    def get_object(self, hash: 'ot.Commitish',
                   type: Literal['commit']) -> 'ot.GitCommit':
        ...
    @overload
    def get_object(self, hash: 'ot.Treeish',
                   type: Literal['tree']) -> 'ot.GitTree':
        ...
    @overload
    def get_object(self, hash: 'ot.Blobish',
                   type: Literal['blob'],
                   size: int=-1) -> 'ot.GitBlob':
        ...
    @overload
    def get_object(self, hash: 'ot.Tagish',
                   type: Literal['tag']) -> 'ot.GitTagObject':
        ...
    @overload
    def get_object(self, hash: 'ot.Objectish',
                   type: Optional[GitObjectType]=None,
                   size: int=-1) -> 'ot.GitObject':
        ...
    def get_object(self, hash: 'ot.Objectish',
                   type: Optional[GitObjectType]=None,
                   size: int=-1) -> 'ot.GitObject':
        '''
        Get an object by its hash. If the type is given, the object is checked
        and cast to the appropriate type. If the type is not given, the object
        is returned as `GitObject`.

        It will, however, be converted to the appropriate type when the object
        is dereferenced.
        '''
        ...

    @abstractmethod
    def get_ref(self, ref: 'rt.RefSpec|None' =None) -> 'rt.GitRef|None':
        '''
        Get a reference (branch, tag, etc.) by name.
        '''
        ...

    @abstractmethod
    def add_reference(self,
                      target: ObjectId,
                      source: 'ot.GitObject|rt.GitRef'):
        '''
        Add a reference to an object.
        '''
        ...

    @abstractmethod
    def open_worktree(self, path: Path|str, /, *,
                    branch: 'rt.GitRef|str|None'=None,
                    commit: 'ot.Commitish|None'=None,
                    **kwargs) -> 'GitWorktree':
        '''
        Open a worktree associated with this repository.
        '''
        ...

    def _add_worktree(self, worktree: 'GitWorktree'):
        '''
        Add a worktree to the repository. Internal use only.
        '''
        ...


@runtime_checkable
class GitWorktree(Jsonable, gc.GitCmd, Protocol):
    """
    A git worktree. This is the root directory of where the files
    are checked out.
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
    def path(self) -> PurePosixPath: ...
    @path.setter
    @abstractmethod
    def path(self, value: PurePosixPath|str): ...

    @property
    @abstractmethod
    def location(self) -> Path:
        '''
        The location of the worktree.
        '''
        ...

    @property
    @abstractmethod
    def branch(self) -> 'rt.GitRef':
        '''
        The current branch checked out in the worktree.

        If no branch is checked out, a `GitNoBranchException` is raised.
        '''
        ...
    @branch.setter
    @abstractmethod
    def branch(self, value: 'rt.GitRef|str|None'):
        '''
        The branch of the worktree. If the worktree is not on a branch,
        set to None.
        '''
        ...


    @property
    @abstractmethod
    def commit(self) -> 'ot.GitCommit':
        '''
        The current commit checked out in the worktree.

        When no commit is checked out, a `GitNoCheckoutException` is raised.
        '''
        ...
    @commit.setter
    @abstractmethod
    def commit(self, value: 'ot.Commitish'): ...


    locked: str
    prunable: str

@runtime_checkable
class GitContext(Jsonable, Protocol):
    """
    A git context.
    """

    @staticmethod
    def get() -> 'GitContext':
        '''
        Get the current context.
        '''
        from xonsh.built_ins import XSH
        assert XSH.env is not None, "Xonsh environment not initialized."
        context = cast(GitContext|None, XSH.env.get('XGIT', None))
        if context is None:
            raise GitException("No git context.")
        return context


    @property
    @abstractmethod
    def objects(self) -> 'Mapping[ot.ObjectId, ot.GitObject]':
        '''
        The objects in the repositories.
        '''
        ...

    @property
    @abstractmethod
    def session(self) -> XonshSession:
        '''
        The `xonsh` session.
        '''
        ...

    @abstractmethod
    def open_repository(self, path: 'Path|str|GitRepository', /, *,
                        select: bool=True
                        ) -> 'GitRepository':
        '''
        Open a git repository.

        PARAMETERS
        ----------
        path : Path | str | GitRepository
            The path to the repository, or a repository object.
        select : bool
            If True, select the repository as the current repository.
            Default: True

        RETURNS
        -------
        GitRepository
            The repository object.
        '''
        ...

    @property
    @abstractmethod
    def worktree(self) -> GitWorktree:
        '''
        The current worktree being explored.

        This is a worktree associated with the current repository.
        If there is no known worktree a `GitException` is raised.

        If there is no current repository, a `GitException` is raised.
        '''
        ...

    @worktree.setter
    @abstractmethod
    def worktree(self, value: 'GitWorktree|None|str|Path'): ...


    @property
    @abstractmethod
    def repository(self) -> GitRepository:
        '''
        The current repository being explored.

        RETURNS
        -------
        GitRepository
            The repository object.
        '''
        ...


    @repository.setter
    @abstractmethod
    def repository(self, value: 'GitRepository|None|str|Path'): ...


    @property
    @abstractmethod
    def path(self) -> PurePosixPath:
        '''
        The path within the worktree that we are exploring.
        '''
        ...

    @path.setter
    @abstractmethod
    def path(self, value: PurePosixPath|str): ...


    @property
    @abstractmethod
    def branch(self) -> 'rt.GitRef':
        '''
        The current branch being explored.
        '''
        ...

    @branch.setter
    @abstractmethod
    def branch(self, value: 'rt.GitRef|str'): ...

    @property
    @abstractmethod
    def commit(self) -> 'ot.GitCommit':
        '''
        The current commit being explored.
        '''
    @commit.setter
    @abstractmethod
    def commit(self, value: 'ot.Commitish'): ...
    @property

    @abstractmethod
    def cwd(self) -> Path:
        '''
        The current working directory. Same as `Path.cwd()`.
        '''
        ...

    @property
    @abstractmethod
    def people(self) -> dict[str, 'people.Person']:
        '''
        The people associated with the repository.
        '''
        ...

    @property
    @abstractmethod
    def object_references(self) -> Mapping[ObjectId, set[GitObjectReference]]:
        '''
        The references associated with the repository.
        '''
        ...


    def add_reference(self,
                      target: ObjectId,
                      repo: GitRepositoryId,
                      ref: ObjectId|PurePosixPath,
                      t: GitReferenceType,
                      /) -> None:
        '''
        Add a reference to an object, so we can find where it is used.

        PARAMETERS
        ----------
        target : ObjectId
            The object being referenced.
        repo : GitRepositoryId
            The repository where the reference is.
        ref : ObjectId | PurePosixPath
            The reference to the object.
        t : GitReferenceType
            The type of reference.
        '''
        ...

    @abstractmethod
    def open_worktree(self, path: Path|str, /, *,
                    repository: Optional[GitRepository|str|Path]=None,
                    branch: Optional['PurePosixPath|str|rt.GitRef']=None,
                    commit: Optional['ot.Commitish']=None,
                    select: bool=True,
                    ) -> 'GitWorktree':
        '''
        Open a worktree associated with this repository.

        PARAMETERS
        ----------
        path : Path | str
            The path to the worktree.
        repository : GitRepository | str | Path
            The repository associated with the worktree.
            If not given, the current repository is used.
        branch : PurePosixPath | str | rt.GitRef
            The branch to explore.
        commit : ot.Commitish
            The commit to explore. If not given, the current commit is used.
        select : bool
            If True, select the worktree as the current worktree.
            Default: True

        '''
        ...