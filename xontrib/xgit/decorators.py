"""
Various decorators for xgit commands and functions.

"""

from re import sub
from typing import (
    Any, Generic, MutableMapping, Optional, Callable, Union, Literal,
    TypeVar, TypeAlias,
)
from inspect import signature, Signature, Parameter
import sys
from pathlib import Path

from xonsh.completers.tools import (
    contextual_completer, ContextualCompleter, CompletionContext,
)
from xonsh.completers.completer import add_one_completer, RichCompletion
from xonsh.completers.path import (
    complete_path,
    complete_dir as _complete_dir,
    _complete_path_raw
)
from xonsh.parsers.completion_context import CompletionContext

from xontrib.xgit import vars as xv
from xontrib.xgit.types import CleanupAction, GitHash
from xontrib.xgit.vars import XSH, XGIT, XGIT_OBJECTS
from xontrib.xgit.git_types import (
    Branch, Tag, RemoteBranch, GitRef,
)
from xontrib.xgit.procs import _run_lines

_Suffix = TypeVar('_Suffix', bound=str)

try:
    type  Directory = Path|str
    '''
    A directory path.
    '''
    type File[_Suffix] = Path
    type PythonFile = File[Literal['.py']]
except:
    # We typecheck with 3.12 or newer, but need runtime compatibility with 3.10
    globals()['Directory'] = Path|str
    class _FileMarker(Generic[_Suffix]):
        "Marker to distinguish File from Path"
        @classmethod
        def suffix(cls) -> _Suffix:
            ...
    globals()['File'] = str|Path|_FileMarker
    globals()['PythonFile'] = str|Path|_FileMarker[Literal['.py']]

@contextual_completer
def complete_hash(context: CompletionContext) -> set:
    return set(XGIT_OBJECTS.keys())

def complete_ref(prefix: str = "") -> ContextualCompleter:
    '''
    Returns a completer for git references.
    '''
    @contextual_completer
    def completer(context: CompletionContext) -> set[str]:
        refs = _run_lines(["git", "for-each-ref", "--format=%(refname)", prefix])
        return set(refs)
    return completer

@contextual_completer
def complete_dir(context: CompletionContext) -> tuple[set, int]:
    """
    Completer for directories.
    """
    if context.command:
        return _complete_dir(context.command)
    elif context.python:
        line = context.python.prefix
        # simple prefix _complete_path_raw will handle gracefully:
        prefix = line.rsplit(" ", 1)[-1]
        return _complete_path_raw(prefix, line, len(line) - len(prefix), len(line), {},
                                  filtfunc=lambda x: Path(x).is_dir())
    return set(), 0

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

class CmdError(Exception):
    '''
    An exception raised when a command fails, that should be
    caught and handled by the command, not the shell.
    '''
    pass

def command(
    cmd: Optional[Callable] = None,
    flags: frozenset = frozenset(),
    for_value: bool = False,
    alias: Optional[str] = None,
    export: bool = False,
    prefix_cmd: Optional[Callable[..., Any]]=None,
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
            
        def type_completer(p: Parameter):
            match p.annotation:
                case t if t == Path or t == Union[Path, str]:
                    return complete_path
                case t if t == Directory:
                    return complete_dir
                case t if t == PythonFile:
                    # For now. We will filter later.
                    return complete_path
                case t if t == Branch:
                    return complete_ref("refs/heads")
                case t if t == Tag:
                    return complete_ref("refs/tags//")
                case t if t == RemoteBranch:
                    return complete_ref("refs/remotes/")
                case t if t == GitRef:
                    return complete_ref()
                case t if t == GitHash:
                    return complete_hash
                case t if isinstance(t, TypeAlias) and getattr(t, '__base__') == File:
                    return complete_path
        
        for p in sig.parameters.values():
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
                            raise ValueError(f"Missing value for {p.name}")  # noqa
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
                            raise CmdError(f"Missing value for {p.name}")
                        n_kwargs[p.name] = value
                    case p.VAR_POSITIONAL:
                        if len(args) > 0:
                            n_args.extend(args)
                            args.clear()
                    case p.VAR_KEYWORD:
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
        except CmdError as ex:
            try:
                if env.get("XGIT_TRACE_ERRORS"):
                    import traceback
                    traceback.print_exc()
            except Exception:
                pass
            print(f"{ex!s}", file=stderr)
        return ()

    # @wrap(cmd) copies the signature, which we don't want.
    wrapper.__name__ = cmd.__name__
    wrapper.__qualname__ = cmd.__qualname__
    wrapper.__doc__ = cmd.__doc__
    wrapper.__module__ = cmd.__module__
    _aliases[alias] = wrapper
    if export:
        _export(cmd)
    if prefix_cmd is not None:
        prefix_cmd._subcmds[alias] = wrapper
    return cmd

def prefix_command(alias: str):
    """
    Create a command that invokes other commands selected by prefix.
    """
    subcmds: dict[str, Callable[..., Any|None]] = {}
    @command(alias=alias)
    def prefix_cmd(args, **kwargs):
        if len(args) == 0 or args[0] not in subcmds:
            print(f"Usage: {alias} <subcommand> ...", file=sys.stderr)
            for subcmd in subcmds:
                print(f"  {subcmd}", file=sys.stderr)
            return
        subcmd = args[0]
        args = args[1:]
        return subcmd(args, **kwargs)
    prefix_name = alias.replace("-", "_")
    import inspect
    module = inspect.stack()[1].__module__
    qual_name = f'{module}.{prefix_name}'
    setattr(prefix_cmd, "__name__", prefix_name)
    setattr(prefix_cmd, "__qualname__", qual_name)
    setattr(prefix_cmd, "__module__", module)
    setattr(prefix_cmd, "__doc__", f"Invoke a subcommand of {alias}")
    setattr(prefix_cmd, '_subcmds', subcmds)
    _aliases[alias] = prefix_cmd
    @contextual_completer
    def completer(ctx: CompletionContext):
        return set(subcmds.keys())
    add_one_completer(prefix_name, completer)
    return prefix_cmd

xgit = prefix_command("xgit")
