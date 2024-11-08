'''
Implementations of the `GitObject family of classes.

These are the core objects that represent the contents of a git repository.
'''

from typing import (
    MutableMapping, Optional, Literal, Sequence, Any, Protocol, cast, TypeAlias,
    Callable,
)
from datetime import datetime
import re

from xonsh.built_ins import XSH
from xonsh.tools import chdir

from xontrib.xgit.types import (
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
from xontrib.xgit.entries import _GitTreeEntry
# Avoid a circular import dependency by not looking
# at the vars module until it is loaded.
from xontrib.xgit import vars as xv
from xontrib.xgit.procs import (
    _run_binary, _run_text, _run_lines, _run_stream
)

GitContextFn: TypeAlias = Callable[[], GitContext]

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
        **kwargs,
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


class _GitObject(_GitId, GitObject):
    """
    Any object stored in a git repository. Holds the hash and type of the object.
    """
    _size: int|GitLoader
    @property
    def size(self) -> int:
        if callable(self._size):
            self._size()
            return self.size
        return self._size

    def __init__(
        self,
        hash: GitHash,
        size=-1,
        /,
        loader: Optional[GitLoader] = None,
        context: GitContext|GitContextFn = lambda: cast(GitContext,xv.XGIT),
    ):
        _GitId.__init__(
            self,
            hash,
            loader=loader,
            context=context,
        )
        if size >= 0:
            self._size = size
        else:
            assert loader is not None, "Size must be provided if no loader"
            self._size = loader

    @property
    def type(self):
        raise NotImplementedError("Must be implemented in a subclass")

    def __format__(self, fmt: str):
        return f"{self.type} {super().__format__(fmt)}"

    def _repr_pretty_(self, p, cycle):
        p.text(f"{type(self).__name__.strip('_')}({self.hash})")
xv.__dict__['_GitObject'] = _GitObject

def _parse_git_entry(
    line: str,
    context: GitContext|GitContextFn = lambda: cast(GitContext,xv.XGIT),
parent: GitHash | None = None
) -> tuple[str, GitTreeEntry]:
    if callable(context):
        context = context()
    """
    Parse a line from `git ls-tree --long` and return a `GitObject`.
    """
    mode, type, hash, size, name = line.split()
    mode = cast(GitEntryMode, mode)
    type = cast(GitObjectType, type)
    return _git_entry(hash, name, mode, type, size, context, parent)


def _git_entry(
    hash: GitHash,
    name: str,
    mode: GitEntryMode,
    type: GitObjectType,
    size: str|int,
    context: GitContext|GitContextFn = lambda: cast(GitContext,xv.XGIT),
    parent: str | None = None,
) -> tuple[str, GitTreeEntry]:
    if callable(context):
        context = context()
    """
    Obtain or create a `GitObject` from a parsed entry line or equivalent.
    """
    assert isinstance(XSH.env, MutableMapping), f"XSH.env() not a mapping: {XSH.env!r}"
    if XSH.env.get("XGIT_TRACE_OBJECTS"):
        args = f"{hash=}, {name=}, {mode=}, {type=}, {size=}, {context=}, {parent=}"
        msg = f"git_entry({args})"
        print(msg)

    entry = xv.XGIT_OBJECTS.get(hash)
    if type == "tree":
        obj = _GitTree(hash, context=context)
    elif type == "blob":
        obj = _GitBlob(hash, int(size), context=context)
    elif type == "commit":
        obj = _GitCommit(hash, context=context)
    elif type == "tag":
        obj = _GitTagObject(hash, context=context)
    else:
        raise ValueError(f"Unknown type {type}")
    xv.XGIT_OBJECTS[hash] = obj
    entry = _GitTreeEntry(obj, name, mode)
    if context is not None:
        key = (context.reference(name), parent)
        xv.XGIT_REFERENCES[hash].add(key)
    return name, entry


class _GitTree(_GitObject, GitTree, dict[str, _GitObject]):
    """
    A directory ("tree") stored in a git repository.

    This is a read-only dictionary of the entries in the directory as well as being
    a git object.

    Updates would make no sense, as this would invalidate the hash.
    """

    _lazy_loader: GitLoader | None
    def __init__(
        self,
        tree: GitHash,
        /,
        *,
        context: GitContext|GitContextFn = lambda: cast(GitContext, xv.XGIT),
    ):
        if callable(context):
            context = context()
        context = context.new_context()
        def _lazy_loader():
            with chdir(context.worktree):
                for line in _run_lines(["git", "ls-tree", "--long", tree]):
                    if line:
                        name, entry = _parse_git_entry(line, context, tree)
                        dict.__setitem__(self, name, entry)
            self._lazy_loader = None
        self._lazy_loader = _lazy_loader

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
        return dict.__len__(self)

    def __contains__(self, key):
        self._expand()
        return dict.__contains__(self, key)

    def __getitem__(self, key: str) -> _GitObject:
        self._expand()
        return dict.__getitem__(self, key)

    def __setitem__(self, key: str, value: _GitObject):
        raise NotImplementedError("Cannot set items in a GitTree")

    def __delitem__(self, key: str):
        raise NotImplementedError("Cannot delete items in a GitTree")

    def __iter__(self):
        self._expand()
        return dict.__iter__(self)

    def __bool__(self):
        return len(self) > 0

    def __reversed__(self):
        self._expand()
        return super().__reversed__()

    def items(self):
        self._expand()
        return dict.items(self)

    def keys(self):
        self._expand()
        return dict.keys(self)

    def values(self):
        self._expand()
        return dict.values(self)

    def get(self, key: str, default: Any = None):
        self._expand()
        return dict.get(self, key, default)

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
        context: GitContext|GitContextFn = lambda: cast(GitContext, xv.XGIT),
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
        return _run_binary(["git", "cat-file", "blob", self.hash]).stdout

    @property
    def stream(self):
        """
        Return the contents of the file.
        """
        return _run_stream(["git", "cat-file", "blob", self.hash])

    @property
    def lines(self):
        return _run_lines(["git", "cat-file", "blob", self.hash])

    @property
    def text(self):
        return _run_text(["git", "cat-file", "blob", self.hash])

_RE_AUTHOR = re.compile(r"^(([^<]+) [<]([^>+])[>]) (\d+) ([+-]\d{4})$")

def _parse_author_date(line: str) -> tuple[str, str, str, datetime]:
    """
    Parse a line from a git commit and return the author info and the date.

    returns: author, name, email, date
    """
    m = _RE_AUTHOR.match(line)
    if m is None:
        raise ValueError(f"Could not parse author line: {line}")
    author, name, email, _date, _tz = m.groups()
    tz = datetime.strptime(_tz, "%z").tzinfo
    date = datetime.fromtimestamp(int(_date), tz=tz)
    return author, name, email, date

class _GitCommit(_GitObject, GitCommit):
    """
    A commit in a git repository.
    """

    @property
    def type(self) -> Literal["commit"]:
        return "commit"

    _tree: GitTree|GitLoader
    @property
    def tree(self) -> GitTree:
        if callable(self._tree):
            self._tree()
            return self.tree
        return self._tree

    _parents: Sequence[GitCommit]|GitLoader
    @property
    def parents(self) -> Sequence[GitCommit]:
        if callable(self._parents):
            self._parents()
            return self.parents
        return self._parents

    _message: str|GitLoader
    @property
    def message(self) -> str:
        if callable(self._message):
            self._message()
            return self.message
        return self._message

    _author: str|GitLoader
    @property
    def author(self) -> str:
        if callable(self._author):
            self._author()
            return self.author
        return self._author

    _author_date: datetime|GitLoader
    @property
    def author_date(self) -> datetime:
        if callable(self._author_date):
            self._author_date()
            return self.author_date
        return self._author_date

    _author_email: str|GitLoader
    @property
    def author_email(self) -> str:
        if callable(self._author_email):
            self._author_email()
            return self.author_email
        return self._author_email

    _author_name: str|GitLoader
    @property
    def author_name(self) -> str:
        if callable(self._author_name):
            self._author_name()
            return self.author_name
        return self._author_name

    _committer: str|GitLoader
    @property
    def committer(self) -> str:
        if callable(self._committer):
            self._committer()
            return self.committer
        return self._committer

    _committer_date: datetime|GitLoader
    @property
    def committer_date(self) -> datetime:
        if callable(self._committer_date):
            self._committer_date()
            return self.committer_date
        return self._committer_date

    _committer_email: str|GitLoader
    @property
    def committer_name(self) -> str:
        if callable(self._committer_name):
            self._committer_name()
            return self.committer_name
        return self._committer_name

    _committer_email: str|GitLoader
    @property
    def committer_email(self) -> str:
        if callable(self._committer_email):
            self._committer_email()
            return self.committer_email
        return self._committer_email

    _signature: str|GitLoader
    @property
    def signature(self) -> str:
        if callable(self._signature):
            self._signature()
            return self.signature
        return self._signature

    def _update_author(self, line: str):
        author, name, email, date = _parse_author_date(line)
        self._author = author
        self._author_name = name
        self._author_email = email
        self._author_date = date

    def _update_committer(self, line: str):
        committer, name, email, date = _parse_author_date(line)
        self._committer = committer
        self._committer_name = name
        self._committer_email = email
        self._committer_date = date

    def __init__(self, hash: str, /, *, context: GitContext|GitContextFn = lambda: cast(GitContext, xv.XGIT)):
        if callable(context):
            context = context()
        context = context.new_context(commit=hash)

        def loader():
            with chdir(context.worktree):
                lines = _run_lines(["git", "cat-file", "commit", hash])
                tree = next(lines).split()[1]
                self._tree = _GitTree(tree, context=context)
                self._parents = []
                for line in lines:
                    if line.startswith("parent"):
                        self._parents.append(_GitCommit(line.split()[1], context=context))
                    elif line.startswith("author"):
                        author_loader = lambda: self._update_author(line.split(maxsplit=1)[1])
                        self._author = author_loader
                        self._author_name = author_loader
                        self._author_email = author_loader
                        self._author_date = author_loader
                    elif line.startswith("committer"):
                        committer_loader = lambda: self._update_committer(line.split(maxsplit=1)[1])
                        self._committer = committer_loader
                        self._committer_name = committer_loader
                        self._committer_email = committer_loader
                        self._committer_date = committer_loader
                    elif line == "":
                        break
                    else:
                        raise ValueError(f"Unexpected line: {line}")
                msg_lines = []
                sig_lines = []
                for line in lines:
                    if line == "-----BEGIN PGP SIGNATURE-----":
                        sig_lines.append(line)
                        break
                    msg_lines.append(line)
                self._message = "\n".join(msg_lines)
                sig_lines.extend(lines)
                self._signature = "\n".join(sig_lines)
            self._tree = loader
            self._parents = loader
            self._author = loader
            self._author_name = loader
            self._author_email = loader
            self._author_date = loader
            self._committer = loader
            self._committer_name = loader
            self._committer_email = loader
            self._committer_date = loader
            self._message = loader
            self._signature = loader


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

    _object: GitObject|GitLoader
    @property
    def object(self) -> GitObject:
        if callable(self._object):
            self._object()
            return self.object
        return self._object

    _tagger: str|GitLoader
    @property
    def tagger(self) -> str:
        if callable(self._tagger):
            self._tagger()
            return self.tagger
        return self._tagger

    _tagger_email: str|GitLoader
    @property
    def tagger_email(self) -> str:
        if callable(self._tagger_email):
            self._tagger_email()
            return self.tagger
        return self._tagger_email

    _tagger_name: str|GitLoader
    @property
    def tagger_name(self) -> str:
        if callable(self._tagger_name):
            self._tagger_name()
            return self.tagger
        return self._tagger_name

    _tag_type: GitObjectType|GitLoader
    @property
    def tag_type(self) -> str:
        if callable(self._tag_type):
            self._tag_type()
            return self.tag_type
        return self._tag_type

    _tag_name: str|GitLoader
    @property
    def tag_name(self) -> str:
        if callable(self._tag_name):
            self._tag_name()
            return self.tag_name
        return self._tag_name

    _created: datetime|GitLoader
    @property
    def created(self) -> datetime:
        if callable(self._created):
            self._created()
            return self.created
        return self._created

    _message: str|GitLoader
    @property
    def message(self) -> str:
        if callable(self._message):
            self._message()
            return self.message
        return self._message

    _signature: str|GitLoader
    @property
    def signature(self) -> str:
        if callable(self._signature):
            self._signature()
            return self.signature
        return self._signature

    def __init__(self, hash: str, /, *,
                 context: GitContext|GitContextFn = lambda: cast(GitContext, xv.XGIT)):
        def loader():
            nonlocal context
            context = context.new_context(commit=hash)
            with chdir(context.worktree):
                lines = _run_lines(["git", "cat-file", "tag", hash])
                for line in lines:
                    if line.startswith("object"):
                        self._object = _GitObject(line.split()[1], context=context)
                    elif line.startswith("type"):
                        tag_type = line.split()[1]
                        assert tag_type in ("commit", "tree", "blob", "tag")
                        self._tag_type = tag_type
                    elif line.startswith("tag"):
                        self._tag_name = line.split(maxsplit=1)[1]
                    elif line.startswith("tagger"):
                        tagger_line = line.split(maxsplit=1)[1]
                        def parse_tagger(line):
                            tagger, name, email, date = _parse_author_date(line)
                            self._tagger = tagger
                            self._tagger_name = name
                            self._tagger_email = email
                            self._created= date
                        loader2 = lambda: parse_tagger(line.split(maxsplit=1)[1])
                        self._tagger = loader2
                        self._tagger_name = loader2
                        self._tagger_email = loader2
                        self._created = loader2
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
                self._message = "\n".join(msg_lines)
                for line in lines:
                    sig_lines.append(line)
                self._signature = "\n".join(sig_lines)
            self._object = loader
            self._tagger = loader
            self._tagger_name = loader
            self._tagger_email = loader
            self._created = loader
            self._message = loader
            self._signature = loader

        _GitObject.__init__(self, hash, context=context, loader=loader)

    def __str__(self):
        return f"tag {self.hash}"

    def __repr__(self):
        return f"GitTag({self.hash!r})"

    def __format__(self, fmt: str):
        return f"tag {self.hash.format(fmt)}"

if __name__ == '__main__':
    t = _GitTree("hash")