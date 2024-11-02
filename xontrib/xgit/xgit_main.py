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
from typing import Mapping, Optional, cast, Any
from collections.abc import Callable
from inspect import signature, Signature
import builtins
import sys

from xonsh.built_ins import XSH, XonshSession
from xonsh.events import events
from xonsh.tools import chdir
from xonsh.procs.pipelines import HiddenCommandPipeline

from xontrib.xgit.xgit_types import (
    CleanupAction,
    GitTree,
)
from xontrib.xgit.xgit_context import (
    _git_context,
    _relative_to_home,
)
from xontrib.xgit.xgit_objects import (
    _git_entry,
)
from xontrib.xgit.xgit_vars import (
    _set_xgit,
    _xgit_counter,
)
from xontrib.xgit import xgit_vars as xv

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

_unload_actions: list[CleanupAction] = []

_aliases: dict[str, Callable] = {}
"""
Dictionary of aliases defined on loading this xontrib.
"""

_exports: dict[str, Any] = {}
"""
Dictionary of functions or other values defined here to loaded into the xonsh context.
"""

def _export(cmd: Any | str, name: Optional[str] = None):
    """
    Decorator to mark a function or value for export.
    This makes it available from the xonsh context, and is undone
    when the xontrib is unloaded.

    If a string is supplied, it is looked up in the xgit_var module's globals.
    For other, non-function values, supply the name as the second argument.
    """
    if name is None and isinstance(cmd, str):
        name = cmd
        cmd = xv.__dict__[cmd]
    if name is None:
        name = getattr(cmd, "__name__", None)
    if name is None:
        raise ValueError("No name supplied and no name found in value")
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


def command(
    cmd: Optional[Callable] = None,
    flags: frozenset = frozenset(),
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
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
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
        for p in sig.parameters.values():

            def add_arg(value: Any):
                match p.kind:  # noqa
                    case p.POSITIONAL_ONLY:  # noqa
                        n_args.append(value)
                    case p.POSITIONAL_OR_KEYWORD:  # noqa
                        positional = len(args) > 0
                        if value == p.empty:  # noqa
                            if positional:
                                value = args.pop(0)
                            elif p.name in kwargs:  # noqa
                                value = kwargs.pop(p.name)  # noqa
                            else:
                                value = p.default  # noqa
                        if value == p.empty:  # noqa
                            raise ValueError(f"Missing value for {p.name}")  # noqa
                        if positional:
                            n_args.append(value)
                        else:
                            n_kwargs[p.name] = value  # noqa
                    case p.KEYWORD_ONLY:  # noqa
                        if value == p.empty:  # noqa
                            if p.name in kwargs:  # noqa
                                value = kwargs.pop(p.name)  # noqa
                            else:
                                value = p.default  # noqa
                        if value == p.empty:  # noqa
                            raise ValueError(f"Missing value for {p.name}")  # noqa
                        n_kwargs[p.name] = value  # noqa
                    case p.VAR_POSITIONAL:  # noqa
                        if len(args) > 0:
                            n_args.extend(args)
                            args.clear()
                    case p.VAR_KEYWORD:  # noqa
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


@command(export=True)
def git_cd(path: str = "", stderr=sys.stderr) -> None:
    """
    Change the current working directory to the path provided.
    If no path is provided, change the current working directory
    to the git repository root.
    """
    if xv.XGIT is None or xv.XGIT.worktree is None:
        XSH.execer.exec(f"cd {path}")
        return
    if path == "":
        xv.XGIT.git_path = Path(".")
    elif path == ".":
        pass
    else:
        git_path = (xv.XGIT.worktree / xv.XGIT.git_path / path).resolve()
        git_path = git_path.relative_to(xv.XGIT.worktree)
        xv.XGIT.git_path = git_path
    fpath = xv.XGIT.worktree / xv.XGIT.git_path
    try:
        xv.XSH.execer.exec(f"cd {fpath}")
    except Exception as ex:
        print(f"Could not change to {fpath}: {ex}", file=stderr)


@command(
    for_value=True,
)
def git_pwd():
    """
    Print the current working directory and git context information if available.
    """
    if xv.XGIT is None:
        print(f"cwd: {_relative_to_home(Path.cwd())}")
        print("Not in a git repository")
        return
    return xv.XGIT


@command(for_value=True, export=True)
def git_ls(path: Path | str = ".", stderr=sys.stderr):
    """
    List the contents of the current directory or the directory provided.
    """
    if xv.XGIT is None:
        raise ValueError("Not in a git repository")
    path = Path(path)
    with chdir(xv.XGIT.worktree or xv.XGIT.repository):
        parent: str | None = None
        if path == Path("."):
            tree = XSH.subproc_captured_stdout(
                ["git", "log", "--format=%T", "-n", "1", "HEAD"]
            )
        else:
            path_parent = path.parent
            if path_parent != path:
                nparent: GitTree = git_ls(path.parent)
                tree = nparent[path.name].hash
                parent = nparent.hash
        _, dir = _git_entry(tree, path.name, "0400", "tree", "-", xv.XGIT, parent)
        return dir.object


_xonsh_displayhook = sys.displayhook
"""
Xonsh's original displayhook.
"""

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
        setattr(builtins, ",", value)
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
    XSH.ctx["+"] = getattr(builtins, "_")  # noqa
    XSH.ctx["++"] = XSH.ctx.get("__")
    XSH.ctx["+++"] = XSH.ctx.get("___")


@events.on_chdir
def update_git_context(olddir, newdir):
    """
    Update the git context when changing directories.
    """
    if xv.XGIT is None:
        # Not set at all so start from scratch
        _set_xgit(_git_context())
        return
    newpath = Path(newdir)
    if xv.XGIT.worktree == newpath:
        # Going back to the worktree root
        xv.XGIT.git_path = Path(".")
    if xv.XGIT.worktree not in newpath.parents:
        # Not in the current worktree, so recompute the context.
        _set_xgit(_git_context())
    else:
        # Fast move within the same worktree.
        xv.XGIT.git_path = Path(newdir).resolve().relative_to(xv.XGIT.worktree)

def xgit_version():
    """
    Return the version of xgit.
    """
    from importlib.metadata import version
    return version("xontrib-xgit")

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
_export("_xgit_counter")


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

    XSH.env['PROMPT_FIELDS']['xgit.version'] = xgit_version

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
    if 'xgit.version' in XSH.env['PROMPT_FIELDS']:
        del XSH.env['PROMPT_FIELDS']['xgit.version']
    return dict()
