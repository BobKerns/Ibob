"""
An reference to a `GitObject` in trees in the repository.

These act as proxies to the actual objects, and provide a way to access
the objects in a more user-friendly way as one navigates the the trees.

The objects which can occur in Git trees are

* `GitBlob` ('blob') which contain the file data.
* `GitTree` ('tree') which provide the directory hierarchy,
* `GitCommit` ('commit'), which are used to reference a commit
    in a submodule.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
"""
from types import MappingProxyType
from typing import Optional, cast, Mapping, Iterator
from pathlib import Path


from xonsh.lib.pretty import RepresentationPrinter
from xontrib.xgit.context_types import GitRepository
import xontrib.xgit.objects as xo
from xontrib.xgit.types import (
    GitEntryMode, GitHash
)
from xontrib.xgit.entry_types import (
    GitEntry, O, ParentObject, EntryObject,
    GitEntryBlob, GitEntryTree, GitEntryCommit,
)
import xontrib.xgit.object_types as ot

class _GitEntry(GitEntry[O]):
    """
    An entry in a git tree. In addition to referencing a `GitObject`,
    it supplies the mode and name, and the tree, commit, or tag that
    it was found in.
    """

    __name: str
    __object: O
    __mode: GitEntryMode
    __path: Optional[Path]
    __parent_object: Optional[ParentObject]
    __parent: Optional['GitEntryTree']
    __repository: GitRepository

    @property
    def type(self):
        return self.__object.type

    @property
    def hash(self) -> GitHash:
        return self.__object.hash

    @property
    def mode(self) -> GitEntryMode:
        return self.__mode

    @property
    def size(self):
        return self.__object.size

    @property
    def object(self) -> O:
        return self.__object

    @property
    def prefix(self):
        """
        Return the prefix for the entry type.
        """
        if self.type == "tree":
            return "D"
        elif self.mode == "120000":
            return "L"
        elif self.mode == "160000":
            return "S"
        elif self.mode == "100755":
            return "X"
        else:
            return"-"

    @property
    def name(self):
        return self.__name

    @property
    def parent_object(self) -> 'ParentObject|None':
        return self.__parent_object

    @property
    def parent(self) -> 'GitEntryTree | None':
        if self.__parent is not None:
            return self.__parent
        if self.__parent_object is None:
            return None
        parent = self.__parent_object
        if parent.type != "tree":
            return None
        parent = cast(xo.GitTree, parent)
        return cast(GitEntryTree, parent.hashes[self.hash])
        #entry = xo._git_entry(parent, self._name, self._mode, self.type, self.size,

    @property
    def repository(self):
        return self.__repository

    @property
    def entry(self):
        rw = self.prefix
        return f"{rw} {self.type} {self.hash}\t{self.name}"

    @property
    def entry_long(self):
        size = str(self.size) if self.size >= 0 else '-'
        rw = self.prefix
        return f"{rw} {self.type} {self.hash} {size:>8s}\t{self.name}"

    @property
    def path(self):
        return self.__path

    def __init__(self,
                 object: O,
                 name: str,
                 mode: GitEntryMode,
                 repository: GitRepository,
                 parent_object: Optional['ParentObject|GitHash']=None,
                 parent: Optional['GitEntryTree']=None,
                 path: Optional[Path] = None):
        self.__object = object
        self.__name = name
        self.__mode = mode
        self.__path = path
        self.__repository = repository
        po = None
        if isinstance(parent_object, str):
            po = cast(ParentObject, xo._git_object(parent_object, repository))
        if parent is not None and parent_object is None:
            po = parent.object
        self.__parent_object = po
        self.__parent = parent
        self.__hashes = {}

    #def __hasattr__(self, name):
    #    return hasattr(self._object, name)


    def __str__(self):
        return f"{self.entry_long} {self.name}"

    def __repr__(self):
        return f"GitTreeEntry({self.name!r}, {self.entry_long!r})"

    def __format__(self, fmt: str):
        return f"{self.entry_long.__format__(fmt)}"

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
        if cycle:
            p.text("GitTreeEntry(...)")
        else:
            with p.group(4, "GitTreeEntry(", ')'):
                p.breakable()
                p.pretty(self.__object)
                p.text(',')
                p.breakable()
                p.text(f'mode={self.mode!r},')
                p.breakable()
                p.text(f'name={self.name!r},')
                p.breakable()
                p.text(f'parent={self.parent.hash if self.parent else None!r},')
                p.breakable()
                p.text(f'path={self.path!r}')


class _GitEntryTree(_GitEntry[ot.GitTree], GitEntryTree):
    @property
    def hashes(self) -> Mapping[GitHash, GitEntry]:
        return MappingProxyType(self.__object.hashes)

    def __getitem__(self, name):
        obj = self.__object[name] # type: ignore
        path = self.__path / name if self.__path else None
        _, entry = xo._git_entry(obj, name, self.__mode, obj.type, obj.size,
                                repository=self.__repository,
                                path=path,
                                parent_entry=self,
                                parent=self.__object)
        return entry

    def get(self, name, default=None):
        self.__object.get(name, default)

    def __contains__(self, name):
        return name in self.__object

    def items(self) -> Iterator[tuple[str, EntryObject]]:
        return self.__object.items()

    def keys(self):
        return self.__object.keys()

    def values(self) -> Iterator[EntryObject]:
        return self.__object.values()

    def __iter__(self):
        return self.__object.__iter__()

    def __len__(self):
        return len(self.__object)

    def __eq__(self, other):# -> Any:
        return self.__object == other

    def __bool__(self):
        return bool(self.__object)

class _GitEntryCommit(_GitEntry[ot.GitCommit], GitEntryCommit):
    @property
    def message(self):
        return self.__object.message

    @property
    def author(self):
        return self.__object.author

    @property
    def committer(self):
        return  self.__object.committer

    @property
    def tree(self):
        return self.__object.tree

    @property
    def parents(self):
        return self.__object.parents

    @property
    def signature(self):
        return self.__object.signature

class _GitEntryBlob(_GitEntry[ot.GitBlob], GitEntryBlob):
    @property
    def data(self):
        return self.__object.data

    @property
    def lines(self):
        return self.__object.lines

    @property
    def stream(self):
        return self.__object.stream
