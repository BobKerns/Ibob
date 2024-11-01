"""
This is a file of utilities initially targeting exploration of git repositories.

It provides the following commands:
- git-cd: Change the current working directory to the path provided.
- git-pwd: Print the current working directory and git context information if available.
- git-ls: List the contents of the current directory or the directory provided.

In addition, it extends the displayhook to provide the following variables:
- _: The last value displayed.
- __: The value displayed before the last one.
- ___: The value displayed before the one before the last one.
- _<m>" The nth value.
"""

from contextlib import suppress
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Sequence, cast, Any
from collections import defaultdict
from collections.abc import Callable
from inspect import signature, Signature
import builtins
import sys
import io

from xonsh.built_ins import XSH, XonshSession
from xonsh.events import events
from xonsh.tools import chdir
from xonsh.procs.pipelines import HiddenCommandPipeline
from xonsh.lib.pretty import PrettyPrinter

__all__ = ()

# Our events:

events.doc(
    "xgit_on_predisplay",
    "Runs before displaying the result of a command with the value to be displayed.",
)
events.doc(
    "xgit_on_postdisplay",
    "Runs after displaying the result of a command with the value displayed.",
)

# Good start! Get more documentation -> https://xon.sh/contents.html#guides,

type CleanupAction = Callable[[], None]
"""
An action to be taken when the xontrib is unloaded.
"""
_unload_actions: list[CleanupAction] = []

_aliases: dict[str, Callable] = {}
"""
Dictionary of aliases defined on loading this xontrib.
"""

_exports: dict[str, Any] = {}
"""
Dictionary of functions or other values defined here to loaded into the xonsh context.
"""


def _export(cmd: Any | str, name: Optional[str] = None) -> Callable:
    """
    Decorator to mark a function or value for export.
    This makes it available from the xonsh context, and is undone
    when the xontrib is unloaded.

    If a string is supplied, it is looked up in this module's globals.
    For other, non-function values, supply the name as the second argument.
    """
    if name is None and isinstance(cmd, str):
        name = cmd
        cmd = globals()[cmd]
    if name is None:
        name = cmd.__name__
    _exports[name] = cmd
    return cmd


def _do_unload_actions():
    """
    Unload a value supplied by the xontrib.
    """
    for action in _unload_actions:
        try:
            action()
        except Exception:
            from traceback import print_exc

            print_exc()


def _run_stdout(cmd: Sequence[str]) -> str:
    """
    Run a command and return the standard output.
    """
    if XSH.env.get("XGIT_TRACE_COMMANDS"):
        print(f'Running {' '.join(cmd)}', file=sys.stderr)
    return XSH.subproc_captured_stdout([*cmd, ("2>", "/dev/null")])


def _run_object(cmd: Sequence[str]) -> io.StringIO:
    """
    Run a command and return the standard output as an iterator.

    Throws an exception if the command fails.
    """
    if XSH.env.get("XGIT_TRACE_COMMANDS"):
        print(f'Running {' '.join(cmd)}', file=sys.stderr)
    return XSH.subproc_captured_object([*cmd, ("2>", "/dev/null")]).itercheck()


def command(
    cmd: Optional[Callable] = None,
    flags: set = frozenset(),
    for_value: bool = False,
    alias: Optional[str] = None,
    export: bool = False,
) -> Callable:
    """
    Decorator/decorator factory to make a function a command. Command-line
    flags and arguments are passed to the function as keyword arguments.

    - `flags` is a set of strings that are considered flags. Flags do not
    take arguments. If a flag is present, the value is True.

    - If `for_value` is True, the function's return value is used as the
    return value of the command. Otherwise, the return value will be
    a hidden command pipeline.

    - `alias` gives an alternate name for the command. Otherwise a name is
    constructed from the function name.

    - `export` makes the function available from python as well as a command.

    EXAMPLES:

    @command
    def my_command(args, stdin, stdout, stderr):
        ...

    @command(flags={'a', 'b'})
    def my_command(args, stdin, stdout, stderr):
        ...

    @command(for_value=True)
    def my_command(*args, **kwargs):
        ...
    """
    if cmd is None:
        return lambda cmd: command(
            cmd,
            flags=flags,
            for_value=for_value,
            alias=alias,
            export=export,
        )
    if alias is None:
        alias = cmd.__name__.replace("_", "-")

    def wrapper(
        args,
        stdin: io.TextIOBase = sys.stdin,
        stdout: io.TextIOBase = sys.stdout,
        stderr: io.TextIOBase = sys.stderr,
        **kwargs,
    ):
        if "--help" in args:
            print(getattr(cmd, "__doc__", ""), file=stderr)
            return
        while len(args) > 0:
            if args[0] == "--":
                args.pop(0)
                break
            if args[0].startswith("--"):
                if "=" in args[0]:
                    k, v = args.pop(0).split("=", 1)
                    kwargs[k[2:]] = v
                else:
                    if args[0] in flags:
                        kwargs[args.pop(0)[2:]] = True
                    else:
                        kwargs[args.pop(0)[2:]] = args.pop(0)
            else:
                break

        sig: Signature = signature(cmd)
        n_args = []
        n_kwargs = {}
        for param in sig.parameters.values():
            p = param

            def add_arg(value: Any):
                match p.kind:
                    case p.POSITIONAL_ONLY:
                        n_args.append(value)
                    case p.POSITIONAL_OR_KEYWORD:
                        positional = len(args) > 0
                        if value == p.empty:
                            if positional:
                                value = args.pop(0)
                            elif p.name in kwargs:
                                value = kwargs.pop(p.name)
                            else:
                                value = p.default
                        if value == p.empty:
                            raise ValueError(f"Missing value for {p.name}")
                        if positional:
                            n_args.append(value)
                        else:
                            n_kwargs[p.name] = value
                    case p.KEYWORD_ONLY:
                        if value == p.empty:
                            if p.name in kwargs:
                                value = kwargs.pop(p.name)
                            else:
                                value = p.default
                        if value == p.empty:
                            raise ValueError(f"Missing value for {p.name}")
                        n_kwargs[p.name] = value
                    case p.VAR_POSITIONAL:
                        if len(args) > 0:
                            n_args.extend(args)
                            args.clear()
                    case p.VAR_KEYWORD:
                        n_args.update(
                            {"stdin": stdin, "stdout": stdout, "stderr": stderr}
                        )

            match p.name:
                case "stdin":
                    add_arg(stdin)
                case "stdout":
                    add_arg(stdout)
                case "stderr":
                    add_arg(stderr)
                case "args":
                    add_arg(args)
                case _:
                    add_arg(kwargs.get(p.name, p.empty))
        try:
            val = cmd(*n_args, **n_kwargs)
            if for_value:
                if XSH.env.get("XGIT_TRACE_DISPLAY"):
                    print(f"Returning {val}", file=stderr)
                XSH.ctx["_XGIT_RETURN"] = val
        except Exception as ex:
            print(f"Error running {alias}: {ex}", file=stderr)
        return ()

    # @wrap(cmd) copies the signature, which we don't want.
    wrapper.__name__ = cmd.__name__
    wrapper.__qualname__ = cmd.__qualname__
    wrapper.__doc__ = cmd.__doc__
    wrapper.__module__ = cmd.__module__
    _aliases[alias] = wrapper
    if export:
        _export(cmd)
    return cmd


type ContextKey = tuple[Path, Path, str, str]

type GitLoader = Callable[[], None]
"""
A function that loads the contents of a git object.
"""

type GitEntryMode = Literal[
    "040000",  # directory
    "100755",  # executable
    "100644",  # normal file
    "160000",  # submodule
    "20000",  # symlink
]
"""
The valid modes for a git tree entry.
"""

type GitObjectType = Literal["blob", "tree", "commit", "tag"]
"""
Valid types for a git object.
"""

type GitHash = str
"""
A git hash. Defined as a string to make the code more self-documenting.
"""


@dataclass
class GitRepository:
    """
    A git repository.
    """

    repository: Path = Path(".git")
    """
    The path to the repository. If this is a worktree,
    it is the path to the worktree-specific part.
    For the main worktree, this is the same as `common`.
    """
    common: Path = Path(".git")
    """
    The path to the common part of the repository. This is the same for all worktrees.
    """


@dataclass
class GitWorktree(GitRepository):
    """
    A git worktree. This is the root directory of where the files are checked out.
    """

    worktree: Path | None = Path(".")


@dataclass
class GitContext(GitWorktree):
    """
    Context for working within a git repository.

    This tracks the current branch, commit, and path within the commit's
    tree.
    """

    git_path: Path = Path(".")
    branch: str = ""
    commit: str = ""

    def reference(self, subpath: Optional[Path | str] = None) -> ContextKey:
        key = self.worktree or self.repository
        if subpath is None:
            return (key, self.git_path, self.branch, self.commit)
        return (key, subpath, self.branch, self.commit)

    @property
    def cwd(self) -> Path:
        return Path.cwd()

    def new_context(
        self,
        /,
        worktree: Optional[Path] = None,
        repository: Optional[Path] = None,
        common: Optional[Path] = None,
        git_path: Optional[Path] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> "GitContext":
        worktree = worktree or self.worktree
        repository = repository or self.repository
        common = common or self.common
        git_path = git_path or self.git_path
        branch = branch if branch is not None else self.branch
        commit = commit or self.commit
        return GitContext(
            worktree=worktree,
            repository=repository,
            common=common,
            git_path=git_path,
            branch=branch,
            commit=commit,
        )

    def _repr_pretty_(self, p: PrettyPrinter, cycle: bool):
        if cycle:
            p.text(f"GitContext({self.worktree} {self.git_path}")
        else:
            with p.group(4, "GitTree:"):
                p.break_()
                p.text(f"worktree: {relative_to_home(self.worktree)}")
                p.break_()
                p.text(f"repository: {relative_to_home(self.repository)}")
                p.break_()
                p.text(f"common: {relative_to_home(self.common)}")
                p.break_()
                p.text(f"path: {self.git_path}")
                p.break_()
                p.text(f"branch: {self.branch}")
                p.break_()
                p.text(f"commit: {self.commit}")
                p.break_()
                p.text(f"cwd: {relative_to_home(Path.cwd())}")


XGIT: GitContext | None = None
"""
The current `GitContext` for the session,
or none if not in a git repository or worktree.
"""

XGIT_CONTEXTS: dict[Path, GitContext] = {}
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""


def _set_xgit(xgit: GitContext | None) -> GitContext | None:
    """
    Set the xgit context, making it available in the xonsh context,
    and storing it in the context map.
    """
    global XGIT
    XSH.ctx["XGIT"] = XGIT = xgit
    if xgit is not None:
        XGIT_CONTEXTS[xgit.worktree or xgit.repository] = xgit
    return xgit


def _git_context():
    """
    Get the git context based on the current working directory,
    updating it if necessary.

    The result should generally be passed to `_set_xgit`.
    """

    def multi_params(*params: str) -> Sequence[str]:
        """
        Use `git rev-parse` to get multiple parameters at once.
        """
        val = _run_stdout(["git", "rev-parse", *params])
        if val:
            result = val.strip().split("\n")
        else:
            # Try running them individually.
            result = [_run_stdout(["git", "rev-parse", param]) for param in params]
        if len(result) == 1:
            # Otherwise we have to assign like `value, = multi_params(...)`
            # The comma is` necessary to unpack the single value
            # but is confusing and easy to forget
            # (or not understand if you don't know the syntax).
            result = result[0]
        return result

    in_tree, in_git = multi_params("--is-inside-work-tree", "--is-inside-git-dir")
    try:
        if in_tree == "true":
            # Inside a worktree
            worktree, repository, common, commit = multi_params(
                "--show-toplevel",
                "--absolute-git-dir",
                "--git-common-dir",
                "HEAD",
            )
            worktree = Path(worktree).resolve()
            repository = Path(repository)
            common = repository / common
            git_path = Path.cwd().relative_to(worktree)
            branch = XSH.subproc_captured_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            if worktree in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[worktree]
                xgit.git_path = git_path
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                return GitContext(
                    worktree=worktree,
                    repository=repository,
                    common=common,
                    git_path=git_path,
                    commit=commit,
                    branch=branch,
                )
        elif in_git == "true":
            # Inside a .git directory or bare repository.
            repository, common = multi_params("--absolute-git-dir", "--git-common-dir")
            repository = Path(repository).resolve()
            common = repository / common
            with chdir(common.parent):
                worktree = multi_params("--show-toplevel")
                worktree = Path(worktree).resolve() if worktree else None
            commits = multi_params("HEAD", "main", "master")
            commits = list(filter(lambda x: x, list(commits)))
            commit = commits[0] if commits else ""
            branch = XSH.subproc_captured_stdout(
                ["git", "name-rev", "--name-only", commit]
            )
            repo = worktree or repository
            if repo in XGIT_CONTEXTS:
                xgit = XGIT_CONTEXTS[repo]
                xgit.commit = commit
                xgit.branch = branch
                return xgit
            else:
                return GitContext(
                    worktree=worktree,
                    repository=repository,
                    common=common,
                    git_path=Path("."),
                    commit=commit,
                    branch=branch,
                )
        else:
            return None
    except Exception as ex:
        if XSH.env.get("XGIT_TRACE_ERRORS"):
            import traceback

            traceback.print_exc()
        print(f"Error setting git context: {ex}", file=sys.stderr)
    return None


@command(export=True)
def git_cd(path: str = "", stderr=sys.stderr) -> None:
    """
    Change the current working directory to the path provided.
    If no path is provided, change the current working directory
    to the git repository root.
    """
    if XGIT is None:
        XSH.execer.exec(f"cd {path}")
        return
    if path == "":
        XGIT.git_path = Path(".")
    elif path == ".":
        pass
    else:
        git_path = (XGIT.worktree / XGIT.git_path / path).resolve()
        git_path = git_path.relative_to(XGIT.worktree)
        XGIT.git_path = git_path
    fpath = XGIT.worktree / XGIT.git_path
    try:
        XSH.execer.exec(f"cd {fpath}")
    except Exception as ex:
        print(f"Could not change to {fpath}: {ex}", file=stderr)


def relative_to_home(path: Path) -> Path:
    """
    Get a path for display relative to the home directory.
    This is for display only.
    """
    home = Path.home()
    if path == home:
        return Path("~")
    if path == home.parent:
        return Path(f"~{home.name}")
    try:
        return Path("~") / path.relative_to(home)
    except ValueError:
        return path


@command(
    for_value=True,
)
def git_pwd():
    """
    Print the current working directory and git context information if available.
    """
    if XGIT is None:
        print(f"cwd: {relative_to_home(Path.cwd())}")
        print("Not in a git repository")
        return
    return XGIT


class GitId:
    """
    Anything that has a hash in a git repository.
    """

    _lazy_loader: GitLoader | None
    hash: str

    def __init__(
        self,
        hash: str,
        /,
        *,
        loader: Optional[GitLoader] = None,
        context: GitContext = XGIT,
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


class GitObject(GitId):
    """
    Any object stored in a git repository. Holds the hash and type of the object.
    """

    git_type: GitObjectType

    def __init__(
        self,
        mode: str,
        type: str,
        hash: str,
        /,
        loader: Optional[GitLoader] = None,
        context: GitContext = XGIT,
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


def parse_git_entry(
    line: str, context: GitContext = XGIT, parent: str | None = None
) -> GitObject:
    """
    Parse a line from `git ls-tree --long` and return a `GitObject`.
    """
    mode, type, hash, size, name = line.split()
    return git_entry(name, mode, type, hash, size, context, parent)


def git_entry(
    name: str,
    mode: str,
    type: str,
    hash: str,
    size: str,
    context: GitContext = XGIT,
    parent: str | None = None,
) -> tuple[str, GitObject]:
    """
    Obtain or create a `GitObject` from a parsed entry line or equivalent.
    """
    if XSH.env.get("XGIT_TRACE_OBJECTS"):
        args = f"{name=}, {mode=}, {type=}, {hash=}, {size=}, {context=}, {parent=}"
        msg = f"git_entry({args})"
        print(msg)
    entry = XGIT_OBJECTS.get(hash)
    if entry is not None:
        return name, entry
    if type == "tree":
        entry = GitTree(hash, context=context)
    elif type == "blob":
        entry = GitBlob(mode, hash, size, context=context)
    else:
        # We don't currently handle tags or commits (submodules)
        raise ValueError(f"Unknown type {type}")
    XGIT_OBJECTS[hash] = entry
    key = (context.reference(name), parent)
    XGIT_REFERENCES[hash].add(key)
    return name, entry


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
        context: GitContext = XGIT,
    ):
        def _lazy_loader():
            nonlocal context
            context = context.new_context()
            with chdir(context.worktree):
                for line in _run_object(["git", "ls-tree", "--long", tree]).itercheck():
                    if line:
                        name, entry = parse_git_entry(line, context, tree)
                        dict.__setitem__(self, name, entry)
            self._lazy_loader = None

        dict.__init__(self)
        GitObject.__init__(
            self,
            "0400",
            "tree",
            tree,
            loader=_lazy_loader,
            context=context,
        )

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
        mode,
        hash,
        size,
        /,
        *,
        context: GitContext = XGIT,
    ):
        super().__init__(
            mode,
            "blob",
            hash,
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

    def __init__(self, hash: str, /, *, context: GitContext = XGIT):
        super().__init__(hash)

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

    def __init__(self, hash: str, /, *, context: GitContext = XGIT):
        super().__init__(hash)

    def __str__(self):
        return f"tag {self.hash}"

    def __repr__(self):
        return f"GitTag({self.hash!r})"

    def __format__(self, fmt: str):
        return f"tag {self.hash.format(fmt)}"


XGIT_OBJECTS: dict[str, GitObject] = {}
"""
All the git entries we have seen.
"""

type GitObjectReference = tuple[ContextKey, GitObject | None]
"""
A reference to a git object in a tree in a repository.
"""


class GitTreeEntry:
    """
    An entry in a git tree.
    """

    object: GitObject
    _mode: GitEntryMode

    @property
    def git_type(self):
        return self.object.type

    @property
    def hash(self):
        return self.object.hash

    @property
    def mode(self):
        return self._mode

    def __init__(self, name: str, object: GitObject):
        self.name = name
        self.object = object

    def __str__(self):
        return f"{self.entry} {self.name}"

    def __repr__(self):
        return f"GitTreeEntry({self.name!r}, {self.entry!r})"

    def __format__(self, fmt: str):
        return f"{self.entry.__format__(fmt)} {self.name}"


XGIT_REFERENCES: dict[str, set[GitObjectReference]] = defaultdict(set)
"""
A map to where an object is referenced.
"""


@command(for_value=True, export=True)
def git_ls(path: Path | str = ".", stderr=sys.stderr):
    """
    List the contents of the current directory or the directory provided.
    """
    if XGIT is None:
        raise ValueError("Not in a git repository")
    path = Path(path)
    with chdir(XGIT.worktree or XGIT.repository):
        parent: GitTree | None = None
        if path == Path("."):
            tree = XSH.subproc_captured_stdout(
                ["git", "log", "--format=%T", "-n", "1", "HEAD"]
            )
        else:
            path_parent = path.parent
            if path_parent != path:
                parent = git_ls(path.parent)
                tree = parent[path.name].hash
        _, dir = git_entry(path, "0400", "tree", tree, "-", XGIT, parent)
        return cast(GitTree, dir)


_xonsh_displayhook = sys.displayhook


def _xgit_displayhook(value: Any):
    """
    Add handling for value-returning commands, pre- and post-display events,
    and exception protection.
    """
    ovalue = value
    if isinstance(value, HiddenCommandPipeline):
        value = XSH.ctx.get("_XGIT_RETURN", value)
        if "_XGIT_RETURN" in XSH.ctx:
            if XSH.env.get("XGIT_TRACE_DISPLAY"):
                print("clearing _XGIT_RETURN in XSH.ctx", file=sys.stderr)
            del XSH.ctx["_XGIT_RETURN"]
        else:
            if XSH.env.get("XGIT_TRACE_DISPLAY"):
                msg = (
                    "No _XGIT_RETURN, "
                    + "result has been displayed with str() and suppressed"
                )
                print(msg, file=sys.stderr)

    if XSH.env.get("XGIT_TRACE_DISPLAY") and ovalue is not value:
        sys.stdout.flush()
        print(
            f"DISPLAY: {ovalue=!r} {value=!r} type={type(ovalue).__name__}", sys.stderr
        )
        sys.stderr.flush()
    try:
        events.xgit_on_predisplay.fire(value=value)
        sys.stdout.flush()
        _xonsh_displayhook(value)
        events.xgit_on_postdisplay.fire(value=value)
    except Exception as ex:
        print(ex, file=sys.stderr)
        sys.stderr.flush()


# Set up the notebook-style convenience history variables.

_xgit_counter = XSH.ctx.get("_xgit_counter", None) or iter(range(sys.maxsize))
_count: int = next(_xgit_counter)
_export("_xgit_counter")


@events.xgit_on_predisplay
def _xgit_on_predisplay(value: Any):
    """
    Update the notebook-style convenience history variables before displaying a value.
    """
    global _count
    if (
        value is not None
        and not isinstance(value, HiddenCommandPipeline)
        and XSH.env.get("XGIT_ENABLE_NOTEBOOK_HISTORY")
    ):
        _count = next(_xgit_counter)
        ivar = f"_i{_count}"
        ovar = f"_{_count}"
        XSH.ctx[ivar] = XSH.ctx["-"]
        XSH.ctx[ovar] = value
        print(f"{ovar}: ", end="")


@events.xgit_on_postdisplay
def _xgit_on_postdisplay(value: Any):
    """
    Update _, __, and ___ after displaying a value.
    """
    if value is not None and not isinstance(value, HiddenCommandPipeline):
        builtins._ = value
        XSH.ctx["__"] = XSH.ctx["+"]
        XSH.ctx["___"] = XSH.ctx["++"]


@events.on_precommand
def _on_precommand(cmd: str):
    """
    Before running a command, save our temporary variables.
    We associate them with the session rather than the module.
    These names are deliberately impossible to use, and are named
    after similar variables long used in REPLs.

    _, __, and ___ are the last three values displayed, and are
    directly useful. The variables here are simply to facilitate
    updating those values.
    """
    if "_XGIT_RETURN" in XSH.ctx:
        if XSH.env.get("XGIT_TRACE_DISPLAY"):
            print("Clearing _XGIT_RETURN before command", file=sys.stderr)
        del XSH.ctx["_XGIT_RETURN"]
    XSH.ctx["-"] = cmd.strip()
    XSH.ctx["+"] = builtins._
    XSH.ctx["++"] = XSH.ctx.get("__")
    XSH.ctx["+++"] = XSH.ctx.get("___")


@events.on_chdir
def update_git_context(olddir, newdir):
    """
    Update the git context when changing directories.
    """
    if XGIT is None:
        # Not set at all so start from scratch
        _set_xgit(_git_context())
        return
    newpath = Path(newdir)
    if XGIT.worktree == newpath:
        # Going back to the worktree root
        XGIT.git_path = Path(".")
    if XGIT.worktree not in newpath.parents:
        # Not in the current worktree, so recompute the context.
        _set_xgit(_git_context())
    else:
        # Fast move within the same worktree.
        XGIT.git_path = Path(newdir).resolve().relative_to(XGIT.worktree)


# Export the functions and values we want to make available.

_export("XGIT_CONTEXTS")
_export("XGIT_OBJECTS")
_export("XGIT_REFERENCES")
_export(None, "+")
_export(None, "++")
_export(None, "+++")
_export(None, "-")
_export(None, "__")
_export(None, "___")


def _load_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """
    this function will be called when loading/reloading the xontrib.

    Args:
        xsh: the current xonsh session instance, serves as the interface to
            manipulate the session.
            This allows you to register new aliases, history backends,
            event listeners ...
        **kwargs: it is empty as of now. Kept for future proofing.
    Returns:
        dict: this will get loaded into the current execution context
    """

    XSH.env["XGIT_TRACE_LOAD"] = XSH.env.get("XGIT_TRACE_LOAD", False)
    # Set the initial context on loading.
    _set_xgit(_git_context())
    _export("XGIT")
    if "_XGIT_RETURN" in XSH.ctx:
        del XSH.ctx["_XGIT_RETURN"]

    # Install our displayhook
    global _xonsh_displayhook
    hook = _xonsh_displayhook
    xsh = XSH

    def unhook_display():
        sys.displayhook = hook

    _unload_actions.append(unhook_display)
    _xonsh_displayhook = hook
    sys.displayhook = _xgit_displayhook

    def set_unload(
        ns: Mapping[str, Any],
        name: str,
        value=None,
    ):
        old_value = None
        if name in ns:
            old_value = ns[name]

            def restore_item():
                ns[name] = old_value

            _unload_actions.append(restore_item)
        else:

            def del_item():
                with suppress(KeyError):
                    del ns[name]

            _unload_actions.append(del_item)

    for name, value in _exports.items():
        set_unload(xsh.ctx, name, value)
    for name, value in _aliases.items():
        set_unload(xsh.aliases, name, value)
        xsh.aliases[name] = value

    if "XGIT_ENABLE_NOTEBOOK_HISTORY" not in XSH.env:
        XSH.env["XGIT_ENABLE_NOTEBOOK_HISTORY"] = True

    if XSH.env.get("XGIT_TRACE_LOAD"):
        print("Loaded xontrib-xgit", file=sys.stderr)
    return _exports


def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """Clean up on unload."""
    if XSH.env.get("XGIT_TRACE_LOAD"):
        print("Unloading xontrib-xgit", file=sys.stderr)
    _do_unload_actions()

    if "_XGIT_RETURN" in XSH.ctx:
        del XSH.ctx["_XGIT_RETURN"]

    sys.displayhook = _xonsh_displayhook

    def remove(event: str, func: Callable):
        try:
            getattr(events, event).remove(func)
        except ValueError:
            pass
        except KeyError:
            pass

    remove("on_precommand", _on_precommand)
    remove("on_chdir", update_git_context)
    remove("xgit_on_predisplay", _xgit_on_predisplay)
    remove("xgit_on_postdisplay", _xgit_on_postdisplay)
    # Remember this across reloads.
    XSH.ctx["_xgit_counter"] = _xgit_counter
    if XSH.env.get("XGIT_TRACE_LOAD"):
        print("Unloaded xontrib-xgit", file=sys.stderr)
