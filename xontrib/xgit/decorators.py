"""
Various decorators for xgit commands and functions.

"""

from typing import Any, MutableMapping, Optional, Callable
from inspect import signature, Signature
from functools import partial
import sys

from xontrib.xgit import vars as xv
from xontrib.xgit.types import CleanupAction
from xontrib.xgit.vars import XSH


_unload_actions: list[CleanupAction] = []
"""
Actions to take when unloading the module.
"""

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
        cmd = xv.__dict__.get(cmd, None)
    if name is None:
        name = getattr(cmd, "__name__", None)
    if name is None:
        raise ValueError("No name supplied and no name found in value")
    _exports[name] = cmd
    return cmd

_aliases: dict[str, Callable] = {}
"""
Dictionary of aliases defined on loading this xontrib.
"""

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
        env = XSH.env
        assert isinstance(env, MutableMapping),\
            f"XSH.env not a MutableMapping: {env!r}"
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
                        n_kwargs.update(
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
                if env.get("XGIT_TRACE_DISPLAY"):
                    print(f"Returning {val}", file=stderr)
                XSH.ctx["_XGIT_RETURN"] = val
        except Exception as ex:
            try:
                if env.get("XGIT_TRACE_ERRORS"):
                    import traceback
                    traceback.print_exc()
            except Exception:
                pass
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