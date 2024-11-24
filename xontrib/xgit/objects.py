'''
Implementations of the `GitObject family of classes.

These are the core objects that represent the contents of a git repository.
These are the four types that live in a git object database:

- `GitTree`: A directory of other objects.
- `GitBlob`: A file.
- `GitCommit`: A commit object, representing a snapshot of a submodule.
- `GitTagObject`: A signed tag object. These do not appear in trees,
    but are used to tag commits. (Unsigned tags are just references.)
'''

from multiprocessing import parent_process
from tkinter import TRUE, Entry
from typing import (
    MutableMapping, Optional, Literal, Sequence, Any, cast, TypeAlias,
    Callable, overload, Iterable, Iterator, Mapping
)
from types import MappingProxyType
from pathlib import PurePosixPath
from collections import defaultdict

# Highly dubious for future compatibility
from _collections_abc import dict_items, dict_keys, dict_values

from xonsh.built_ins import XSH
from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.identity_set import IdentitySet
from xontrib.xgit.person import CommittedBy
from xontrib.xgit.types import (
    GitLoader,
    GitHash,
    GitEntryMode,
    GitObjectType,
    GitEntryKey,
    InitFn,
    _NO_VALUE,
)
from xontrib.xgit.object_types import (
    GitId,
    GitCommit,
    GitObject,
    GitTree,
    GitBlob,
    GitTagObject,
    Objectish,
)
from xontrib.xgit.context_types import GitContext, GitRepository
from xontrib.xgit.entry_types import (
    O, ParentObject, EntryObject, GitEntry, GitEntryTree, GitEntryBlob, GitEntryCommit
)
import xontrib.xgit.entries as xe
import xontrib.xgit.git_cmd as gc

GitContextFn: TypeAlias = Callable[[], GitContext]

class _GitId(GitId):
    """
    Anything that has a hash in a git repository.
    """

    _hash: GitHash
    @property
    def hash(self) -> GitHash:
        return self._hash

    def __init__(
        self,
        hash: GitHash,
        /,
        **kwargs,
    ):
        self._hash = hash

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.hash == other.hash

    def __str__(self):
        return self.hash

    def __repr__(self):
        return f"{type(self).__name__.strip('_')}({self.hash!r})"

    def __format__(self, fmt: str):
        return self.hash.format(fmt)


class _GitObject(_GitId, GitObject):
    """
    Any object stored in a git repository. Holds the hash and type of the object.
    """
    _size: int|InitFn['_GitObject', int]
    @property
    def size(self) -> int:
        if callable(self._size):
            self._size = self._size(self)
        return self._size

    def __init__(
        self,
        hash: GitHash,
        size: int|InitFn['_GitObject',int]=-1,
        /,
    ):
        self._size = size
        _GitId.__init__(
            self,
            hash
        )

    def _size_loader(self, repository: 'gc.GitCmd') -> InitFn['_GitObject',int]:
        '''
        Subclasses can call this when they don't know the size of the object
        '''
        def loader(self: _GitObject):
            size = repository.git_string("cat-file", "-s", self.hash)
            return int(size)
        return loader

    @property
    def type(self):
        raise NotImplementedError("Must be implemented in a subclass")

    def __format__(self, fmt: str):
        return f"{self.type} {super().__format__(fmt)}"

    def _repr_pretty_(self, p, cycle):
        p.text(f"{type(self).__name__.strip('_')}({self.hash})")


class _GitTree(_GitObject, GitTree, dict[str, GitEntry[EntryObject]]):
    """
    A directory ("tree") stored in a git repository.

    This is a read-only dictionary of the entries in the directory as well as being
    a git object.

    Updates would make no sense, as this would invalidate the hash.
    """

    __lazy_loader: InitFn['_GitTree',Iterable[tuple[str,GitEntry]]] | None

    __hashes: defaultdict[GitHash, IdentitySet[GitEntry,int]]
    @property
    def hashes(self) -> Mapping[GitHash, IdentitySet[GitEntry,int]]:
        '''
        A mapping of hashes to the entries that have that hash.
        This will usually be a one-to-one mapping, but it is possible for
        multiple entries to have the same hash. These will have different
        names, even different modes, but the same hash and content.
        '''
        if self.__lazy_loader is not None:
            self._expand()
        return MappingProxyType(self.__hashes)

    def __init__(
        self,
        tree: GitHash,
        /,
        *,
        repository: GitRepository,
    ):
        def _lazy_loader(self: '_GitTree'):
            self.__hashes = defaultdict(lambda: IdentitySet(key=id))
            for line in repository.git_lines("ls-tree", "--long", tree):
                if line:
                    name, entry = self._parse_git_entry(line, repository, tree)
                    self.__hashes[entry.hash].add(entry)
                    yield name, entry
            self.__lazy_loader = None
            self._size = dict.__len__(self)
            for entry in self.values():
                repository.add_reference(entry.hash, entry)
        self.__lazy_loader = _lazy_loader
        dict.__init__(self)
        _GitObject.__init__(
            self,
            tree,
            lambda _: len(self._expand()),
        )
        ent = xe._GitEntryTree(self, '.', "040000", repository, PurePosixPath())
        dict.__setitem__(self, '.', ent)

    def _expand(self):
        if self.__lazy_loader is not None:
            i = self.__lazy_loader(self)
            dict.update(self, i)
        return self

    @property
    def type(self) -> Literal["tree"]:
        return "tree"

    def __hash__(self): # type: ignore
        return _GitObject.__hash__(self._expand())

    def __eq__(self, other):
        return _GitObject.__eq__(self._expand(), other)

    def __repr__(self):
        return f"GitTree(hash={self.hash})"

    def __len__(self):
        return dict.__len__(self._expand())

    def __contains__(self, key):
        return dict.__contains__(self._expand(), key)


    def __getitem__(self, key: str) -> GitEntry[EntryObject]:
        path = key.split("/")
        loc = self
        ent = self['.']
        for p in path:
            match p:
                case '' | '.':
                    pass
                case '..':
                    raise KeyError("Cannot use '..' in a path")
                case _:
                    ent = dict.__getitem__(loc, p)
                    loc = ent.object
        return ent

    def __setitem__(self, key: str, value: GitEntry[EntryObject]):
        raise NotImplementedError("Cannot set items in a GitTree")

    def __delitem__(self, key: str):
        raise NotImplementedError("Cannot delete items in a GitTree")

    def __iter__(self) -> Iterator[str]:
        return dict.__iter__(self._expand())

    def __bool__(self):
        return len(self._expand()) > 0

    def __reversed__(self) -> Iterator[str]:
        self._expand()
        return super().__reversed__()

    def items(self):
        return dict.items(self._expand())

    def keys(self):
        return dict.keys(self._expand())

    def values(self):
        return dict.values(self._expand())

    def get(self, key: str|PurePosixPath, default: Any = None) -> 'GitEntry[xe.EntryObject]':
        self._expand()
        ex = next(iter(dict.values(self)))
        repository = ex.repository
        _, loc = self._git_entry(self.hash, '.', "040000", "tree", -1,
                              repository=repository)

        key_path = PurePosixPath(key)
        path = PurePosixPath()
        for p in key_path.parts:
            if p in ('', '.'):
                continue
            if p == '..':
                raise ValueError("Cannot use '..' in a path")
            loc = dict.get(loc.object, p, _NO_VALUE)
            if loc is _NO_VALUE:
                return default
            path = path / p
        return loc

    def __str__(self):
        return f"D {self.hash} {len(self._expand()):>8d}"

    def __format__(self, fmt: str):
        """
        Format a directory for display.
        Format specifier is in two parts separated by a colon.
        The first part is a format string for the entries.
        The second part is a path to the directory.

        The first part can contain:
        - 'l' to format the entries in long format.
        - 'a' to abbreviate the hash to 8 characters.
        - 'd' to format the directory as itself
        """
        if "l" in fmt and "d" not in fmt:
            return "\n".join(
                e.__format__(f"d{fmt}") for e in self._expand().values()
            )
        hash = self.hash[:8] if "a" in fmt else self.hash
        return f"D {hash} {len(self._expand()):>8d}"

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text(f"GitTree({self.hash})")
        else:
            l = len(self._expand())
            with p.group(4, f"GitTree({self.hash!r}, len={l}, '''", "\n''')"):
                for e in self.values():
                    p.break_()
                    if e.type == "tree":
                        rw = "D"
                    elif e.mode == "120000":
                        rw = "L"
                    elif e.mode == "160000":
                        rw = "S"
                    elif e.mode == "100755":
                        rw = "X"
                    else:
                        rw = "-"
                    size = str(e.size) if e.size >= 0 else '-'
                    suffix = '/' if e.type == 'tree' else ''
                    l = f'{rw} {e.hash} {size:>8s} {e.name}{suffix}'
                    p.text(l)

    def _parse_git_entry(
        self,
        line: str,
        repository: GitRepository,
        parent_hash: GitHash | None = None
    ) -> tuple[str, GitEntry]:
        """
        Parse a line from `git ls-tree --long` and return a `GitObject`.
        """
        mode, type, hash, size, name = line.split()
        mode = cast(GitEntryMode, mode)
        type = cast(GitObjectType, type)
        parent = repository.get_object(parent_hash) if parent_hash is not None else None
        size = int(size)
        return self._git_entry(hash, name, mode, type, size, repository, parent)


    @overload
    def _git_entry(
        self,
        hash_or_obj: GitHash|GitCommit,
        name: str,
        mode: GitEntryMode,
        type: Literal['commit'],
        size: int,
        repository: GitRepository,
        parent: Optional[GitObject] = None,
        parent_entry: Optional[GitEntryTree] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, GitEntryCommit]: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: GitHash|GitBlob,
        name: str,
        mode: GitEntryMode,
        type: Literal['blob'],
        size: int,
        repository: GitRepository,
        parent: Optional[GitObject] = None,
        parent_entry: Optional[GitEntryTree] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, GitEntryBlob]: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: GitHash|GitTree,
        name: str,
        mode: GitEntryMode,
        type: Literal['tree'],
        size: int,
        repository: GitRepository,
        parent: Optional[GitObject] = None,
        parent_entry: Optional[GitEntryTree] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, GitEntryTree]: ...

    @overload
    def _git_entry(
        self,
        hash_or_obj: GitHash|O,
        name: str,
        mode: GitEntryMode,
        type: GitObjectType,
        size: int,
        repository: GitRepository,
        parent: Optional[GitObject] = None,
        parent_entry: Optional[GitEntryTree] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, GitEntry[O]]: ...

    # Implementation
    def _git_entry(
        self,
        hash_or_obj: GitHash|O,
        name: str,
        mode: GitEntryMode,
        type: GitObjectType,
        size: int,
        repository: GitRepository,
        parent: Optional[GitObject] = None,
        parent_entry: Optional[GitEntryTree] = None,
        path: Optional[PurePosixPath] = None,
    ) -> tuple[str, GitEntry[O]]:
        """
        Obtain or create a `GitObject` from a parsed entry line or equivalent.
        """
        assert isinstance(XSH.env, MutableMapping),\
            f"XSH.env not a MutableMapping: {XSH.env!r}"
        parent_hash = parent.hash if parent is not None else ''

        match hash_or_obj:
            case str():
                hash: Objectish = hash_or_obj
                obj = repository.get_object(hash, type, size=size)
            case GitObject():
                obj = hash_or_obj
                hash = obj.hash
            case _:
                raise ValueError(f"Invalid hash or object: {hash_or_obj}")

        if XSH.env.get("XGIT_TRACE_OBJECTS"):
            args = f"{hash=}, {name=}, {mode=}, {type=}, {size=}, {repository.path=}, {parent=}"
            msg = f"git_entry({args})"
            print(msg)
        if path is not None:
            this_path = path / name
        else:
            this_path = PurePosixPath() / name
        match type:
            case 'tree':
                entry = xe._GitEntryTree(cast(GitTree, obj), name, mode,
                            repository=repository,
                            path=this_path,
                            parent=parent_entry,
                            parent_object=cast(ParentObject, parent))
            case 'blob':
                entry = xe._GitEntryBlob(cast(GitBlob, obj), name, mode,
                            repository=repository,
                            path=this_path,
                            parent=parent_entry,
                            parent_object=cast(ParentObject, parent))
            case 'commit':
                entry = xe._GitEntryCommit(cast(GitCommit, obj), name, mode,
                            repository=repository,
                            path=this_path,
                            parent=parent_entry,
                            parent_object=cast(ParentObject, parent))
            case _:
                raise ValueError(f"Unknown type {type}")
        return name, cast(GitEntry[O], entry)


class _GitBlob(_GitObject, GitBlob):
    """
    A file ("blob") stored in a git repository.
    """

    __repository: GitRepository
    '''
    A repository that contains the blob. Any repository with the blob will do,
    this does not constitute part of the blob's identity. We just need a repo
    with an object database containing it, to access the data.
    '''

    @property
    def type(self) -> Literal["blob"]:
        return "blob"

    def __init__(
        self,
        hash: GitHash,
        size: int|InitFn[_GitObject,int]=-1,
        /,
        *,
        repository: GitRepository,
    ):
        if isinstance(size, int) and size < 0:
            size = self._size_loader(repository)
        _GitObject.__init__(
            self,
            hash,
            size,
        )
        self.__repository = repository

    def __str__(self):
        return f"{self.type} {self.hash} {self.size:>8d}"

    def __repr__(self):
        return f"GitFile({self.hash!r})"

    def __len__(self):
        return self.size

    def __format__(self, fmt: str):
        """
        Format a file for display.
        Format specifier is in two parts separated by a colon.
        The first part is a format string for the output.
        The second part is a path to the file.

        As files don't have inherent names, the name must be provided
        in the format string by the directory that contains the file.
        If no path is provided, the hash is used.

        The format string can contain:
        - 'l' to format the file in long format.
        """
        hash = self.hash[:8] if "a" in fmt else self.hash
        if "l" in fmt:
            return f"{hash} {self.size:>8d}"
        return hash

    def _repr_pretty_(self, p, cycle):
        p.text(f"GitBlob({self.hash!r}, {self.size})")

    @property
    def data(self) -> bytes:
        """
        Return the contents of the file.
        """
        return self.__repository.git_binary("cat-file", "blob", self.hash).read()

    @property
    def stream(self):
        """
        Return the contents of the file.
        """
        return self.__repository.git_stream("cat-file", "blob", self.hash)

    @property
    def lines(self):
        return self.__repository.git_lines("cat-file", "blob", self.hash)

    @property
    def text(self):
        return self.__repository.git_stream("cat-file", "blob", self.hash,
                                            text=True,
                                            ).read()

class _GitCommit(_GitObject, GitCommit):
    """
    A commit in a git repository.
    """
    __loader: GitLoader|None
    @property
    def type(self) -> Literal["commit"]:
        return "commit"

    __tree: GitTree|InitFn[GitCommit, GitTree]
    @property
    def tree(self) -> GitTree:
        if self.__loader:
            self.__loader()
        if callable(self.__tree):
            self.__tree = self.__tree(self)
        return self.__tree

    __parents: Sequence[GitCommit]
    @property
    def parents(self) -> Sequence[GitCommit]:
        if self.__loader:
            self.__loader()
        return self.__parents

    __message: str
    @property
    def message(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__message

    __author: CommittedBy
    __committer: CommittedBy
    @property
    def author(self):
        if self.__loader:
            self.__loader()
        return self.__author
    @property
    def committer(self):
        if self.__loader:
            self.__loader()
        return self.__committer

    __signature: str
    @property
    def signature(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__signature

    def __init__(self, hash: str, /, *, repository: GitRepository):
        def loader():
            lines = repository.git_lines("cat-file", "commit", hash)
            tree = next(lines).split()[1]
            def load_tree(_):
                return repository.get_object(tree, 'tree')
            self.__tree = load_tree
            self.__parents = []
            in_sig = False
            msg_lines = []
            sig_lines = []
            for line in lines:
                if line.startswith("parent"):
                    self.__parents.append(repository.get_object(line.split()[1], 'commit'))
                elif line.startswith("author"):
                    author_line = line.split(maxsplit=1)[1]
                    self.__author = CommittedBy(author_line,
                                                repository=repository)
                elif line.startswith("committer"):
                    committer_line = line.split(maxsplit=1)[1]
                    self.__committer = CommittedBy(committer_line,
                                                   repository=repository)
                elif line == 'gpgsig -----BEGIN PGP SIGNATURE-----':
                    in_sig = True
                    sig_lines.append(line)
                elif in_sig:
                    sig_lines.append(line)
                    if line.strip() == "-----END PGP SIGNATURE-----":
                        in_sig = False
                elif line == "":
                    break
                else:
                    raise ValueError(f"Unexpected line: {line}")
            msg_lines.extend(lines)
            self.__message = "\n".join(msg_lines)
            self.__signature = "\n".join(sig_lines)
            self._size = 0
        self.__loader = loader
        _GitObject.__init__(self, hash, self._size_loader(repository))

    def __str__(self):
        return f"commit {self.hash}"

    def __repr__(self):
        return f"GitCommit({self.hash!r})"

    def __format__(self, fmt: str):
        return f"commit {self.hash.format(fmt)}"

    def _repr_pretty_(self, p: RepresentationPrinter, cycle):
        if cycle:
            p.text(f"GitCommit({self.hash!r})")
        else:
            with p.group(4, f"GitCommit({self.hash!r}, ", "\n)"):
                p.breakable()
                p.text(f"tree={self.tree.hash!r}")
                p.breakable()
                with p.group(4, "parents=[", "],"):
                    for parent in self.parents:
                        p.text(f"{parent.hash},")
                        p.breakable()
                p.breakable()
                p.text(f"author='{self.author.person.full_name} @ {self.author.date}',")
                p.breakable()

                p.text(f"committer='{self.committer.person.full_name} @ {self.committer.date}',")
                p.breakable()
                with p.group(4, "message='''", "''',"):
                    for i, line in enumerate(self.message.splitlines()):
                        p.text(line)
                        if i < len(self.message.splitlines()) - 1:
                            p.break_()
                p.breakable()
                with p.group(4, "signature='''", "'''"):
                    for i, line in enumerate(self.signature.splitlines()):
                        p.text(line)
                        if i < len(self.signature.splitlines()) - 1:
                            p.break_()


class _GitTagObject(_GitObject, GitTagObject):
    """
    A tag in a git repository.
    This is an actual signed tag object, not just a reference.
    """

    __loader: GitLoader|None

    @property
    def type(self) -> Literal["tag"]:
        return "tag"

    __object: GitObject|InitFn[GitTagObject, GitObject]
    @property
    def object(self) -> GitObject:
        if self.__loader:
            self.__loader() # type: ignore
        if callable(self.__object):
            self.__object = self.__object(self)
        return self.__object

    __tagger: CommittedBy
    @property
    def tagger(self) -> CommittedBy:
        if self.__loader:
            self.__loader()
        return self.__tagger

    __tag_type: GitObjectType
    @property
    def tag_type(self) -> GitObjectType:
        if self.__loader:
            self.__loader()
        return self.__tag_type

    __tag_name: str
    @property
    def tag_name(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__tag_name

    __message: str
    @property
    def message(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__message

    __signature: str
    @property
    def signature(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__signature

    def __init__(self, hash: str, /, *,
                 repository: GitRepository):
        def loader():
            lines = repository.git_lines("cat-file", "tag", hash)
            for line in lines:
                if line.startswith("object"):
                    def load_object(_):
                        return repository.get_object(line.split()[1])
                    self.__object = load_object
                elif line.startswith("type"):
                    tag_type = line.split()[1]
                    assert tag_type in ("commit", "tree", "blob", "tag")
                    self.__tag_type = tag_type
                elif line.startswith("tag"):
                    self.__tag_name = line.split(maxsplit=1)[1]
                elif line.startswith("tagger"):
                    tagger_line = line.split(maxsplit=1)[1]
                    self.__tagger = CommittedBy(tagger_line,
                                                repository=repository)
                elif line == "":
                    break
                else:
                    raise ValueError(f"Unexpected line: {line}")
            msg_lines: list[str] = []
            sig_lines: list[str] = []
            for line in lines:
                if line == "-----BEGIN PGP SIGNATURE-----":
                    sig_lines.append(line)
                    break
                msg_lines.append(line)
            self.__message = "\n".join(msg_lines)
            for line in lines:
                sig_lines.append(line)
            self.__signature = "\n".join(sig_lines)
        self.__loader = loader
        _GitObject.__init__(self, hash, self._size_loader(repository))

    def __str__(self):
        return f"tag {self.hash}"

    def __repr__(self):
        return f"GitTag({self.hash!r})"

    def __format__(self, fmt: str):
        return f"tag {self.hash.format(fmt)}"

    def _repr_pretty_(self, p: RepresentationPrinter, cycle):
        if cycle:
            p.text(f"GitCommit({self.hash!r})")
        else:
            with p.group(4, f"GitTagObject({self.hash!r}, ", "\n)"):
                p.breakable()
                p.text(f"object=")
                p.pretty(self.object)
                p.breakable()
                p.text(f"tagger='{self.tagger.person.full_name} @ {self.tagger.date}',")
                p.breakable()
                p.text(f"tag_type='{self.tag_type}',")
                p.breakable()
                with p.group(4, "message='''", "''',"):
                    for i, line in enumerate(self.message.splitlines()):
                        p.text(line)
                        if i < len(self.message.splitlines()) - 1:
                            p.break_()
                p.break_()
                with p.group(4, "signature='''", "'''"):
                    for i, line in enumerate(self.signature.splitlines()):
                        p.text(line)
                        if i < len(self.signature.splitlines()) - 1:
                            p.break_()
