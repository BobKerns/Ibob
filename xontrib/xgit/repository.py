'''
Implementation of the `GitRepository` class.
'''

from contextlib import suppress
from pathlib import Path, PurePosixPath
import re
from typing import Literal, Optional, cast, overload
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from operator import xor
from functools import reduce

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import (
    InitFn, GitObjectType, ObjectId, GitRepositoryId,
    TreeId, BlobId, TagId, CommitId,
)
import xontrib.xgit.ref_types as rt
import xontrib.xgit.object_types as ot
import xontrib.xgit.context_types as ct
import xontrib.xgit.worktree as wtree
import xontrib.xgit.objects as obj
from xontrib.xgit.ref import _GitRef
from xontrib.xgit.git_cmd import _GitCmd
from xontrib.xgit.views.json_types import JsonDescriber
from xontrib.xgit.utils import shorten_branch, relative_to_home


DEFAULT_BRANCH=(
    'refs/heads/main',
    'refs/heads/master',
    "HEAD",
    'refs/remotes/origin/HEAD',
)
'''
The intent is to identify a default branch by examining the repository and/or worktree.
'''


RE_HEX = re.compile(r'^[0-9a-f]{6,}$')

class _GitRepository(_GitCmd, ct.GitRepository):
    """
    A git repository.
    """

    __id: GitRepositoryId|InitFn['_GitRepository', GitRepositoryId]
    @property
    def id(self) -> GitRepositoryId:
        if callable(self.__id):
            self.__id = self.__id(self)
        return self.__id

    __context: 'ct.GitContext'
    @property
    def context(self) -> 'ct.GitContext':
        '''
        Our global context remembered locally.
        '''
        return self.__context


    __path: Path
    @property
    def path(self) -> Path:
        """
        The path to the common part of the repository.
        This directory is the same for all worktrees on this repository.
        """
        return self.__path


    __worktrees: 'ct.WorktreeMap|InitFn[_GitRepository,ct.WorktreeMap]'
    @property
    def worktrees(self) -> Mapping[Path, 'ct.GitWorktree']:
        '''
        Read-only view of worktrees known to be associated with this repository.
        Indexed by `Path` objects to the root of the worktree.
        '''
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        return MappingProxyType(self.__worktrees)


    __preferred_worktree: 'ct.GitWorktree|None'
    @property
    def worktree(self) -> 'ct.GitWorktree':
        """
        Get the preferred worktree.

        This is normally the parent of the `.git` directory, but for a bare repository,
        it is the first worktree found.
        """
        if self.__preferred_worktree is not None:
            return self.__preferred_worktree
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        if self.path.name == ".git":
            worktree = self.get_worktree(self.path.parent)

        with suppress(StopIteration):
            worktree = next(iter(self.worktrees.values()))
            if worktree is not None:
                self.__preferred_worktree = worktree
                return worktree
        raise ValueError("No worktrees found for repository")


    def get_worktree(self, key: Path|str) -> 'ct.GitWorktree|None':
        '''
        Get a worktree associated with this repository, located at `key`.

        PARAMETERS
        ----------
        key: Path|str
            The location of the worktree.

        RETURNS
        -------
        ct.GitWorktree|None
            The worktree associated with the repository at `key`.
        '''
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        path = Path(key).resolve()

        worktree = self.__worktrees.get(path)
        if worktree is not None:
            return worktree

        if worktree is not None:
            self.__preferred_worktree = worktree
            return worktree
        commit = self.rev_parse('HEAD')
        branch_name = self.symbolic_ref('HEAD')
        branch = None
        if branch_name:
            branch = _GitRef(branch_name, repository=self)
        worktree = wtree._GitWorktree(
                        location=self.path.parent,
                        repository=self,
                        repository_path=self.path,
                        branch=branch,
                        commit=self.get_object(commit, 'commit'),
                        locked='',
                        prunable='',
                    )
        if self.__preferred_worktree is None:
            self.__preferred_worktree = worktree
        self.__worktrees[self.path.parent] = worktree
        return cast('ct.GitWorktree', worktree)

    __objects: dict[ObjectId, 'ot.GitObject']


    def get_ref(self, ref: 'rt.RefSpec|None' = None) -> 'rt.GitRef|None':
        '''
        Get a reference to a commit (or other object) in the repository.
        i.e. a branch, tag, or other named reference.

        Conceptually, a ref is named by a path beginning with `refs/`.
        '''
        if ref is None:
            ref = DEFAULT_BRANCH
        def check_ref(ref: 'rt.RefSpec') -> 'rt.GitRef|None':
            with suppress(Exception):
                match ref:
                    case PurePosixPath():
                        return check_ref(str(ref))
                    case rt.GitRef():
                        pass
                    case str():
                        ref = ref.strip()
                        if ref:
                            return _GitRef(ref, repository=self.worktree.repository)
                    case Sequence():
                        return next(
                            rr
                            for rr in (self.get_ref(r) for r in ref)
                            if rr is not None
                        )
        return check_ref(ref)

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
                   size: int=-1
                   ) -> 'ot.GitObject':
        ...
    def get_object(self, hash: 'ot.Objectish',
                   type: Optional[GitObjectType]=None,
                   size: int=-1
                   ) -> 'ot.GitObject':
        match hash:
            case ot.GitObject():
                return hash
            case rt.GitRef():
                hash = self.rev_parse(hash.name)
            case str(h):
                h = h.strip()
                if not h:
                    raise ValueError(f"Invalid hash: {h!r}")
                if RE_HEX.match(h):
                    try:
                        hash = self.rev_parse(hash)
                    except ValueError:
                        hash = self.rev_parse(f'refs/heads/{hash}')
                else:
                    if not h.startswith('refs/'):
                        h = f'refs/heads/{hash}'
                    hash = self.rev_parse(h)
            case _:
                raise ValueError(f"Invalid hash: {hash!r}")
        match type:
            case 'commit':
                return obj._GitCommit(hash, repository=self)
            case 'tree':
                return obj._GitTree(TreeId(hash), repository=self)
            case 'blob':
                return obj._GitBlob(BlobId(hash), size, repository=self)
            case 'tag':
                return obj._GitTagObject(TagId(hash), repository=self)
            case None:
                type = cast(GitObjectType, self.git_string('cat-file', '-t', hash))
        return self.get_object(hash, type, size)

    def __init__(self, *args,
                 context: 'ct.GitContext',
                 path: Path = Path(".git"),
                 **kwargs):
        super().__init__(path.parent)
        self.__context = context
        self.__path = path
        def init_id(self: '_GitRepository') -> GitRepositoryId:
            # This is a simple way to get a unique id for the repository.
            # This xor's the hashes of all commits with no parents.
            # It is careful to do so in the positive domain `f'0{x}'`,
            # and it uses xor to ensure order independence.

            # Any repo with the same ID will be clones of each other.
            id = hex(reduce(xor, (
                int(f'0{x}', 16)
                for x in self.git_lines('log', '--format=%H', '--max-parents=0')),
                0))
            return GitRepositoryId(id[2:])
        self.__id = init_id
        self.__preferred_worktree = None
        def init_worktrees(self: '_GitRepository') -> 'ct.WorktreeMap':
            bare: bool = False
            result: dict[Path, ct.GitWorktree] = {}
            worktree: Path = path.parent.resolve()
            branch: rt.GitRef|None = None
            commit: ot.GitCommit|None = None
            locked: str = ''
            prunable: str = ''

            for line in self.git_lines('worktree', 'list', '--porcelain'):
                match line.strip().split(' ', maxsplit=1):
                    case ['worktree', wt]:
                        worktree = Path(wt).resolve()
                    case ['HEAD', c]:
                        id = CommitId(ObjectId(c))
                        commit = self.get_object(id, 'commit')
                        self.__objects[commit.hash] = commit
                    case ['branch', b]:
                        b = b.strip()
                        branch = _GitRef(b, repository=self) if b else None
                    case ['locked', line]:
                        locked = line.strip('"')
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
                        bare = True  # noqa: F841
                    case _ if line.strip() == '':
                        repository_path = Path(self.git_string('rev-parse',
                                                               '--absolute-git-dir'))
                        repository_path = repository_path.resolve()
                        assert commit is not None, "Commit has not been set."
                        result[worktree] = wtree._GitWorktree(
                            location=worktree,
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

    def add_reference(self, target: ObjectId, source: 'ot.GitObject|rt.GitRef'):
        '''
        Add a reference to an object.
        '''
        match source:
            case ot.GitObject():
                match source.type:
                    case 'commit':
                        type = 'commit'
                    case 'tree':
                        type = 'tree'
                    case 'tag':
                        type = 'tag'
                    case _:
                        raise ValueError(f"Invalid object type: {source.type}")
                self.context.add_reference(target, self.id, source.hash, type)
            case rt.GitRef():
                src_path = PurePosixPath(source.name)
                self.context.add_reference(target, self.id, src_path, 'ref')
            case _:
                return

    def open_worktree(self, path: Path|str, /, *,
                    branch: 'rt.GitRef|str|None'=None,
                    commit: 'ot.Commitish|None'=None,
                    **kwargs) -> 'ct.GitWorktree':
        '''
        Open a worktree associated with this repository.
        '''
        return self.context.open_worktree(path,
                                        repository=self,
                                        branch=branch,
                                        commit=commit,
                                        **kwargs)

    def _add_worktree(self, worktree: 'ct.GitWorktree'):
        '''
        Add a worktree to the repository.
        '''
        if callable(self.__worktrees):
            self.__worktrees = self.__worktrees(self)
        if worktree.path not in self.__worktrees:
            self.__worktrees[worktree.location] = worktree

    def to_json(self, describer: JsonDescriber):
        return str(self.path)

    @staticmethod
    def from_json(data: str, describer: JsonDescriber):
        return _GitRepository(data, context=describer.context)

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
        if cycle:
            p.text(f"GitRepository({self.path}")
        else:
            with p.group(4, "Repository:"):
                p.break_()
                p.text(f".path: {relative_to_home(self.path)}")
                p.break_()
                p.text('.worktrees:')
                with p.indent(4):
                    wts = self.worktrees.values()
                    f1 = max(len(str(relative_to_home(wt.location)))
                             for wt in wts)
                    f2 = max(len(shorten_branch(wt.branch.name if wt.branch else '-'))
                             for wt in wts)
                    f4 = max(len(wt.commit.author.person.name)
                             for wt in wts)
                    for wt in self.worktrees.values():
                        p.breakable()
                        branch = shorten_branch(wt.branch.name if wt.branch else '-')
                        author = wt.commit.author
                        rel_location = relative_to_home(wt.location)
                        line = (
                            f"{rel_location!s:{f1}s}: "
                            f"{branch:{f2}s} "
                            f"{wt.commit.hash[:14]} "
                            f"{author.person.name:{f4}s} "
                            f"{author.date}"
                        )
                        p.text(line)
                p.breakable()
                pref = self.worktree
                p.text(f".preferred_worktree: {relative_to_home(pref.location)}")
                p.break_()
                p.text(f".objects: {len(self.__objects)}")
