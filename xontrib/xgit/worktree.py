'''
Worktree implementation.
'''

from pathlib import Path, PurePosixPath

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import GitNoBranchException
from xontrib.xgit.context_types import GitWorktree, GitRepository
from xontrib.xgit.git_cmd import _GitCmd
import xontrib.xgit.ref as ref
import xontrib.xgit.ref_types as rt
from xontrib.xgit.object_types import GitCommit, Commitish
import xontrib.xgit.repository as repo
from xontrib.xgit.to_json import JsonDescriber


class _GitWorktree(_GitCmd, GitWorktree):
    """
    A git worktree. xThis is the root directory of where the files are checked out.
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

    __path: PurePosixPath = PurePosixPath(".")
    @property
    def path(self) -> PurePosixPath:
        return self.__path
    @path.setter
    def path(self, value: PurePosixPath|str):
        self.__path = PurePosixPath(value)
    
    __location: Path
    @property
    def location(self):
        return self.__location

    __branch: 'rt.GitRef|None'
    @property
    def branch(self) -> 'rt.GitRef':
        if self.__branch is None:
            raise GitNoBranchException()
        return self.__branch
    @branch.setter
    def branch(self, value: 'rt.GitRef|str|None'):
        match value:
            case rt.GitRef():
                self.__branch = value
            case str():
                value = value.strip()
                if value:
                    self.__branch =ref. _GitRef(value, repository=self.__repository)
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
    def commit(self, value: Commitish):
        match value:
            case str() | PurePosixPath():
                value = str(value).strip()
                hash = self.rev_parse(value)
                self.__commit = self.repository.get_object(hash, 'commit')
            case GitCommit():
                self.__commit = value
            case _:
                raise ValueError(f'Not a commit: {value}')
    locked: str
    prunable: str

    def __init__(self, *args,
                repository: GitRepository,
                location: Path,
                repository_path: Path,
                branch: 'rt.GitRef|str|None',
                commit: 'Commitish',
                path: PurePosixPath = PurePosixPath("."),
                locked: str = '',
                prunable: str = '',
                **kwargs
            ):
            super().__init__(location)
            self.__repository = repository
            self.__location= location
            self.__repository_path = repository_path
            self.__path = path
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
        repository = repo._GitRepository(Path(data['repository']),
                                         context=describer.context)
        j: str = data["commit"]
        commit,=repository.get_object(j, 'commit'),

        return _GitWorktree(
            repository=repository,
            repository_path=Path(data["repository_path"]),
            location=Path(data["path"]),
            branch=ref._GitRef(data["branch"], repository=describer.repository),
            commit=commit,
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

