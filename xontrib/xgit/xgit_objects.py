'''
Implementations of the `GitObject famil of classes.

These are the core objects that represent the contents of a git repository.
'''

from datetime import datetime
from typing import Optional, Literal, Sequence, Any, Protocol

from xonsh.built_ins import XSH
from xonsh.tools import chdir

from xontrib.xgit.xgit_types import (
    GitLoader,
    GitHash,
    GitEntryMode,
    GitObjectType,
    GitCommit,
    GitContext,
    GitId,
    GitObject,
    GitTree,
    GitBlob,
    GitTagObject,
    GitTreeEntry,
)
from xontrib.xgit.xgit_refs import _GitTreeEntry
from xontrib.xgit.xgit_vars import (
    XGIT,
    XGIT_OBJECTS,
    XGIT_REFERENCES,
)
from xontrib.xgit.xgit_procs import _run_object, _run_stdout

class ObjectMetaclass(type(Protocol)):
    def __instancecheck__(self, instance: Any) -> bool:
        if hasattr(instance, '__object'):
            return isinstance(instance.__object, self)
        return super().__instancecheck__(instance)

class _GitId(GitId):
    """
    Anything that has a hash in a git repository.
    """

    _lazy_loader: GitLoader | None
    _hash: GitHash
    @property
    def hash(self) -> GitHash:
        return self._hash

    def __init__(
        self,
        hash: GitHash,
        /,
        *,
        loader: Optional[GitLoader] = None,
        context: 'Optional[GitContext]' = XGIT,
    ):
        self._hash = hash
        self._lazy_loader = loader

    def _expand(self):
        """
        Load the contents of the object.
        """
        if self._lazy_loader:
            self._lazy_loader()
        return self

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


class _GitObject(_GitId, GitObject, metaclass=ObjectMetaclass):
    """
    Any object stored in a git repository. Holds the hash and type of the object.
    """
    _size: int
    @property
    def size(self) -> int:
        return self._size

    def __init__(
        self,
        hash: GitHash,
        size=-1,
        /,
        loader: Optional[GitLoader] = None,
        context: Optional[GitContext] = XGIT,
    ):
        _GitId.__init__(
            self,
            hash,
            loader=loader,
            context=context,
        )
        self._size = size

    def __format__(self, fmt: str):
        return f"{self.type} {super().__format__(fmt)}"

    def _repr_pretty_(self, p, cycle):
        p.text(f"{type(self).__name__.strip('_')}({self.hash})")


def _parse_git_entry(
    line: str, context: Optional[GitContext] = XGIT, parent: GitHash | None = None
) -> tuple[str, GitTreeEntry]:
    """
    Parse a line from `git ls-tree --long` and return a `GitObject`.
    """
    mode, type, hash, size, name = line.split()
    return _git_entry(hash, name, mode, type, size, context, parent)


def _git_entry(
    hash: GitHash,
    name: str,
    mode: GitEntryMode,
    type: GitObjectType,
    size: str|int,
    context: Optional[GitContext] = XGIT,
    parent: str | None = None,
) -> tuple[str, GitTreeEntry]:
    """
    Obtain or create a `GitObject` from a parsed entry line or equivalent.
    """
    if XSH.env.get("XGIT_TRACE_OBJECTS"):
        args = f"{hash=}, {name=}, {mode=}, {type=}, {size=}, {context=}, {parent=}"
        msg = f"git_entry({args})"
        print(msg)
    entry = XGIT_OBJECTS.get(hash)
    if entry is not None:
        return name, entry
    if type == "tree":
        obj = _GitTree(hash, context=context)
    elif type == "blob":
        obj = _GitBlob(hash, int(size), context=context)
    else:
        # We don't currently handle tags or commits (submodules)
        raise ValueError(f"Unknown type {type}")
    XGIT_OBJECTS[hash] = obj
    entry = _GitTreeEntry(obj, name, mode)
    if context is not None:
        key = (context.reference(name), parent)
        XGIT_REFERENCES[hash].add(key)
    return name, entry


class _GitTree(_GitObject, GitTree, dict[str, _GitObject]):
    """
    A directory ("tree") stored in a git repository.

    This is a read-only dictionary of the entries in the directory as well as being
    a git object.

    Updates would make no sense, as this would invalidate the hash.
    """
    def __init__(
        self,
        tree: GitHash,
        /,
        *,
        context: Optional[GitContext] = XGIT,
    ):
        def _lazy_loader():
            nonlocal context
            context = context.new_context()
            with chdir(context.worktree):
                for line in _run_object(["git", "ls-tree", "--long", tree]):
                    if line:
                        name, entry = _parse_git_entry(line, context, tree)
                        dict.__setitem__(self, name, entry)
            self._lazy_loader = None

        dict.__init__(self)
        _GitObject.__init__(
            self,
            tree,
            loader=_lazy_loader,
            context=context,
        )

    def __hash__(self):
        _GitObject.__hash__(self)

    def __eq__(self, other):
        return _GitObject.__eq__(self, other)

    def __repr__(self):
        return f"GitTree(hash={self.hash})"

    def __len__(self):
        self._expand()
        return super().__len__()

    def __contains__(self, key):
        self._expand()
        return super().__contains__(key)

    def __getitem__(self, key: str) -> _GitObject:
        self._expand()
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: _GitObject):
        raise NotImplementedError("Cannot set items in a GitTree")

    def __delitem__(self, key: str):
        raise NotImplementedError("Cannot delete items in a GitTree")

    def __iter__(self):
        self._expand()
        return super().__iter__()

    def __bool__(self):
        self._expand()
        return super().__bool__()

    def __reversed__(self):
        self._expand()
        return super().__reversed__()

    def __str__(self):
        return f"D {self.hash} {len(self):>8d}"

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
                e.__format__(f"d{fmt}") for e in self.values()
            )
        hash = self.hash[:8] if "a" in fmt else self.hash
        return f"D {hash} {len(self):>8d}"

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text(f"GitTree({self.hash})")
        else:
            with p.group(4, f"GitTree({self.hash!r}, len={len(self)}, '''", "\n''')"):
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
                    l = f'{rw} {self.hash} {size:>8s} {e.name}'
                    p.text(l)


class _GitBlob(_GitObject, GitBlob):
    """
    A file ("blob") stored in a git repository.
    """

    @property
    def type(self) -> Literal["blob"]:
        return "blob"

    def __init__(
        self,
        hash: GitHash,
        size: int=-1,
        /,
        *,
        context: Optional[GitContext] = XGIT,
    ):
        _GitObject.__init__(
            self,
            hash,
            size,
            context=context,
        )

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
    def data(self):
        """
        Return the contents of the file.
        """
        return _run_object(["git", "cat-file", "blob", self.hash], text=True).stdout

    @property
    def stream(self):
        """
        Return the contents of the file.
        """
        return _run_object(["git", "cat-file", "blob", self.hash], text=True).stdout

    @property
    def lines(self):
        return _run_object(["git", "cat-file", "blob", self.hash], text=True).itercheck()

    @property
    def text(self):
        return _run_stdout(["git", "cat-file", "blob", self.hash])


class _GitCommit(_GitObject, GitCommit):
    """
    A commit in a git repository.
    """

    @property
    def type(self) -> Literal["commit"]:
        return "commit"
    _tree: GitTree
    @property
    def tree(self) -> GitTree:
        return self._tree
    _parents: Sequence[GitCommit]
    @property
    def parents(self) -> list[GitCommit]:
        return self._parents
    _message: str
    @property
    def message(self) -> str:
        return self._message
    _author: str
    @property
    def author(self) -> str:
        return self._author
    _author_date: datetime
    @property
    def author_date(self) -> datetime:
        return self._date
    _committer: str
    @property
    def committer(self) -> str:
        return self._committer
    _committer_date: datetime
    @property
    def committer_date(self) -> datetime:
        return self._date

    def __init__(self, hash: str, /, *, context: Optional[GitContext] = XGIT):
        def loader():
            nonlocal context
            context = context.new_context(commit=hash)
            with chdir(context.worktree):
                lines = _run_object(["git", "cat-file", "commit", hash], text=True)
                tree = next(lines).split()[1]
                self.tree = _GitTree(tree, context=context)
                self.parents = []
                for line in lines:
                    if line.startswith("parent"):
                        self.parents.append(_GitCommit(line.split()[1], context=context))
            self._lazy_loader = None

        _GitObject.__init__(self, hash, context=context, loader=loader)

    def __str__(self):
        return f"commit {self.hash}"

    def __repr__(self):
        return f"GitCommit({self.hash!r})"

    def __format__(self, fmt: str):
        return f"commit {self.hash.format(fmt)}"


class _GitTagObject(_GitObject, GitTagObject):
    """
    A tag in a git repository.
    This is an actual signed tag object, not just a reference.
    """
    _object: GitObject
    @property
    def object(self) -> GitObject:
        return self._object
    _tagger: str
    @property
    def tagger(self) -> str:
        return self._tagger
    _created: datetime
    @property
    def created(self) -> datetime:
        return self._created
    _message: str
    @property
    def message(self) -> str:
        return self._message

    def __init__(self, hash: str, /, *, context: Optional[GitContext] = XGIT):
        def loader():
            nonlocal context
            context = context.new_context(commit=hash)
            with chdir(context.worktree):
                lines = _run_object(["git", "cat-file", "tag", hash], text=True)
                for line in lines:
                    if line.startswith("object"):
                        self.object = _GitObject(line.split()[1], context=context)
                    elif line.startswith("type"):
                        self.type = line.split()[1]
                    elif line.startswith("tag"):
                        self.tag = line.split(maxsplit=1)[1]
                    elif line.startswith("tagger"):
                        self.tagger = line.split(maxsplit=1)[1]
                    elif line == "":
                        break
            self._lazy_loader = None
        _GitObject.__init__(self, hash, context=context, loader=loader)

    def __str__(self):
        return f"tag {self.hash}"

    def __repr__(self):
        return f"GitTag({self.hash!r})"

    def __format__(self, fmt: str):
        return f"tag {self.hash.format(fmt)}"

if __name__ == '__main__':
    t = _GitTree("hash")