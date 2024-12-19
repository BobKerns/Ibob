'''
Path-like interface for git objects.
'''

from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath
from typing import Optional

from xonsh.lib.pretty import RepresentationPrinter

import xontrib.xgit.context_types as ct
import xontrib.xgit.object_types as ot
import xontrib.xgit.objects as xo
import xontrib.xgit.ref_types as rt

@dataclass
class PathBase:
    repository: 'ct.GitRepository'
    top: 'ot.EntryObject'
    root_object: Optional['xo.GitCommit|xo.GitTagObject']
    origin: Optional['xo.GitCommit|xo.GitTagObject|rt.GitRef']
    root: Optional['GitPath']=None
    def __post_init__(self):
        if self.root is None:
            self.root = GitPath(
                '.',
                object=self.top,
                base=self,
                )

class GitPath(PurePath):
    '''
    A path-like object that references a git object.
    '''

    __base: PathBase
    __object: 'xo.GitObject'
    _flavour = PurePosixPath._flavour if hasattr(PurePosixPath, '_flavour') else None # type: ignore

    def __init__(self, *args,
                object: 'xo.GitObject',
                base: PathBase,
                **kwargs):
        #super().__init__()
        self.__base = base
        self.__object = object

    def __new__(cls, *args,
                object: 'xo.GitObject',
                base: PathBase,
                **kwargs):
        return super().__new__(cls, *args, **kwargs)

    @property
    def object(self) -> xo.GitObject:
        return self.__object

    @property
    def repository(self) -> 'ct.GitRepository':
        return self.__base.repository

    @property
    def root_object(self) -> Optional['xo.GitCommit|xo.GitTagObject']:
        return self.__base.root_object

    @property
    def top(self) -> 'ot.EntryObject':
        return self.__base.top

    def __str__(self):
        return str(self.__object)

    def __fspath__(self):
        return str(self.__object)

    def __bytes__(self):
        t = self.__object.type
        repo = self.__base.repository
        return bytes(repo.git_binary('cat-file', t, self.__object.hash).read())

    def __eq__(self, other):
        if isinstance(other, GitPath):
            return (
                self.__object.hash == other.__object.hash
                and PurePath.__eq__(self, other)
            )
        return False

    def __hash__(self):
        return hash(self.__object) + hash(PurePath.__hash__(self))

    def __truediv__(self, other):
        return super().__truediv__(other)

    def __rtruediv__(self, other):
        return super().__rtruediv__(other)

    def __repr_pretty__(self, p: RepresentationPrinter):
        with p.group(2, f'{self.__class__.name}(', ')'):
            p.breakable('')
            with p.group(2, '(', ')'):
                p.text(f'{self.repository.path.parent.name},')
                p.breakable()
                p.pretty(self.root or self.top)
            p.pretty(self.repository)
            p.text(', ')
            p.pretty(self)
            p.text(', ')
            p.pretty(self.__object)
            p.text(')')

    def __repr__(self):
        repo = self.__base.repository
        cls = self.__class__.__name__
        return f'{cls}({repo.path.parent.name!r}, {self!r}, {self.__object!r})'