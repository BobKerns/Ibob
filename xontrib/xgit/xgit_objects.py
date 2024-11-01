'''
Implementations of the `GitObject family of classes.

These are the core objects that represent the contents of a git repository.
'''

from typing import Optional, Literal, cast
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.tools import chdir

from xontrib.xgit.xgit_types import (
    GitContext_,
    GitId_,
    GitObject_,
    GitLoader,
    GitHash,
    GitEntryMode,
    GitObjectType,
)
from xontrib.xgit.xgit_vars import (
    XGIT,
    XGIT_OBJECTS,
    XGIT_REFERENCES,
)
from xontrib.xgit.xgit_procs import _run_object

class GitId(GitId_):
    """
    Anything that has a hash in a git repository.
    """

    _lazy_loader: GitLoader | None
    hash: GitHash

    def __init__(
        self,
        hash: GitHash,
        /,
        *,
        loader: Optional[GitLoader] = None,
        context: 'Optional[GitContext_]' = XGIT,
    ):
        self.hash = hash
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
        return f"{type(self).__name__}({self.hash!r})"

    def __format__(self, fmt: str):
        return self.hash.format(fmt)



class GitObject(GitId, GitObject_):
    """
    Any object stored in a git repository. Holds the hash and type of the object.
    """

    git_type: GitObjectType

    def __init__(
        self,
        hash: GitHash,
        mode: GitEntryMode,
        type: GitObjectType,
        /,
        loader: Optional[GitLoader] = None,
        context: Optional[GitContext_] = XGIT,
    ):
        super().__init__(
            hash,
            loader=loader,
            context=context,
        )
        self.mode = mode
        self.type = type

    def __format__(self, fmt: str):
        return f"{self.type} {super().__format__(fmt)}"


def _parse_git_entry(
    line: str, context: Optional[GitContext_] = XGIT, parent: GitHash | None = None
) -> tuple[str, GitObject]:
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
    context: Optional[GitContext_] = XGIT,
    parent: str | None = None,
) -> tuple[str, GitObject]:
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
        entry = GitTree(hash, context=context)
    elif type == "blob":
        entry = GitBlob(hash, mode, size, context=context)
    else:
        # We don't currently handle tags or commits (submodules)
        raise ValueError(f"Unknown type {type}")
    XGIT_OBJECTS[hash] = entry
    if context is not None:
        key = (context.reference(name), parent)
        XGIT_REFERENCES[hash].add(key)
    return name, cast(GitObject, entry)


class GitTree(GitObject, dict[str, GitObject]):
    """
    A directory ("tree") stored in a git repository.

    This is a read-only dictionary of the entries in the directory as well as being
    a git object.

    Updates would make no sense, as this would invalidate the hash.
    """

    git_type: Literal["tree"] = "tree"

    def __init__(
        self,
        tree: str,
        /,
        *,
        context: Optional[GitContext_] = XGIT,
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
        GitObject.__init__(
            self,
            tree,
            "0400",
            "tree",
            loader=_lazy_loader,
            context=context,
        )

    def __hash__(self):
        GitObject.__hash__(self)

    def __eq__(self, other):
        return GitObject.__eq__(self, other)

    def __repr__(self):
        return f"GitTree(hash={self.hash})"

    def __len__(self):
        self._expand()
        return super().__len__()

    def __contains__(self, key):
        self._expand()
        return super().__contains__(key)

    def __getitem__(self, key: str) -> GitObject:
        self._expand()
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: GitObject):
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
        - 'r' to format recursively
        - 'l' to format the entries in long format.
        - 'a' to abbreviate the hash to 8 characters.
        - 'd' to format the directory as itself
        - 'n' to include only the entry names, not the full paths.
        """
        dfmt, *rest = fmt.split(":", 1)
        path = rest[0] if rest else ""

        def dpath(name: str) -> str:
            if "n" not in dfmt:
                return f"{path}/{name}"
            return ""

        if "r" in dfmt:
            return "\n".join(
                e.__format__(f"{dfmt}:{dpath(n)}") for n, e in self.items()
            )
        if "l" in dfmt and "d" not in dfmt:
            return "\n".join(
                e.__format__(f"d{dfmt}:{dpath(n)}") for n, e in self.items()
            )
        hash = self.hash[:8] if "a" in dfmt else self.hash
        return f"D {hash} {len(self):>8d}"

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text(f"GitTree({self.hash})")
        else:
            with p.group(4, f"GitTree({self.hash})[{len(self)}]"):
                for n, e in self.items():
                    p.breakable()
                    p.text(f"{e:ld} {n}")


class GitBlob(GitObject):
    """
    A file ("blob") stored in a git repository.
    """

    git_type: Literal["blob"] = "blob"

    size: int
    "Size in bytes of the file."

    def __init__(
        self,
        hash: GitHash,
        mode: GitEntryMode,
        size: int|str,
        /,
        *,
        context: Optional[GitContext_] = XGIT,
    ):
        super().__init__(
            hash,
            mode,
            "blob",
            context=context,
        )
        self.size = int(size)

    def __str__(self):
        rw = "X" if self.mode == "100755" else "-"
        return f"{rw} {self.hash} {self.size:>8d}"

    def __repr__(self):
        return f"GitFile({self,hash!r})"

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
        dfmt, *rest = fmt.split(":", 1)
        path = f" {rest[0]}" if rest else ""
        rw = "X" if self.mode == "100755" else "-"
        hash = self.hash[:8] if "a" in dfmt else self.hash
        if "l" in dfmt:
            return f"{rw} {hash} {self.size:>8d}{path}"
        return path or hash


class GitCommit(GitId):
    """
    A commit in a git repository.
    """

    git_type: Literal["commit"] = "commit"

    def __init__(self, hash: str, /, *, context: Optional[GitContext_] = XGIT):
        super().__init__(hash, context=context)

    def __str__(self):
        return f"commit {self.hash}"

    def __repr__(self):
        return f"GitCommit({self.hash!r})"

    def __format__(self, fmt: str):
        return f"commit {self.hash.format(fmt)}"


class GitTagObject(GitId):
    """
    A tag in a git repository.
    This is an actual signed tag object, not just a reference.
    """

    git_type: Literal["tag"] = "tag"

    def __init__(self, hash: str, /, *, context: Optional[GitContext_] = XGIT):
        super().__init__(hash, context=context)

    def __str__(self):
        return f"tag {self.hash}"

    def __repr__(self):
        return f"GitTag({self.hash!r})"

    def __format__(self, fmt: str):
        return f"tag {self.hash.format(fmt)}"
