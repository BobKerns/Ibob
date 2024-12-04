"""
Various decorators for xgit commands and functions.

"""

from contextlib import suppress
from collections.abc import Callable, MutableMapping, Sequence
from typing import (
    Any, NamedTuple, Optional, Union,
    cast, TypeVar, ParamSpec,
)
from inspect import signature, Signature, Parameter
from pathlib import Path

from xonsh.completers.tools import (
    contextual_completer, ContextualCompleter, CompletionContext,
)
from xonsh.completers.completer import add_one_completer
from xonsh.completers.path import (
    complete_dir as _complete_dir,
    _complete_path_raw
)
from xonsh.built_ins import XonshSession, XSH as GLOBAL_XSH
from xonsh.events import Event

from xontrib.xgit.types import (
    GitError,
    KeywordInputSpecs,
)
from xontrib.xgit.context_types import GitContext
from xontrib.xgit.invoker import (
    CommandInvoker, PrefixCommandInvoker, SharedSessionInvoker,
    EventInvoker,
)

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
    if name is None:
        name = getattr(cmd, "__name__", None)
    if name is None:
        raise ValueError("No name supplied and no name found in value")
    _exports[name] = cmd
    return cmd

def context(xsh: Optional[XonshSession] = GLOBAL_XSH) -> GitContext:
    if xsh is None:
        raise GitError('No xonsh session supplied.')
    env = xsh.env
    if env is None:
        raise GitError('xonsh session has no env attribute.')
    XGIT = env.get('XGIT')
    if XGIT is None:
        raise GitError('No XGIT context in xonsh session.')
    return cast(GitContext, XGIT)


F = TypeVar('F', bound=Callable)
T =  TypeVar('T')
P = ParamSpec('P')
def session():
    '''
    Decorator to bind functions such as event handlers to a session.

    They receive the session and context as as the keyword arguments:
    XSH=xsh, XGIT=context

    When the plugin is unloaded, the functions are turned into no-ops.
    '''
    def decorator(func: Callable[P,T]) -> Callable[...,T]:
        invoker = SharedSessionInvoker(func)
        return invoker.create_runner()
    return decorator

def event_handler(event: Event):
    '''
    Decorator to bind functions as event handlers to a session.

    They receive the session and context as as the keyword arguments:
    XSH=xsh, XGIT=context

    When the plugin is unloaded, the functions are turned into no-ops.
    '''
    def decorator(func: Callable[P,T]) -> Callable[...,T]:
        return EventInvoker(event, func)
    return decorator


@contextual_completer
@session()
def complete_hash(context: CompletionContext, *, XGIT: GitContext) -> set[str]:
    return set(XGIT.objects.keys())

def complete_ref(prefix: str = "") -> ContextualCompleter:
    '''
    Returns a completer for git references.
    '''

    @contextual_completer
    @session()
    def completer(context: CompletionContext, /, XGIT: GitContext) -> set[str]:
        worktree = XGIT.worktree
        refs = worktree.git_lines("for-each-ref", "--format=%(refname)", prefix)
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

class CommandInfo(NamedTuple):
    """
    Information about a command.
    """
    cmd: Callable
    alias_fn: Callable
    alias: str
    signature: Signature

class InvocationInfo(NamedTuple):
    """
    Information about a command invocation.
    """
    cmd: CommandInfo
    args: Sequence
    kwargs: dict
    stdin: Any
    stdout: Any
    stderr: Any
    env: MutableMapping

class CmdError(Exception):
    '''
    An exception raised when a command fails, that should be
    caught and handled by the command, not the shell.
    '''
    pass

def nargs(p: Callable):
    """
    Return the number of positional arguments accepted by the callable.
    """
    return len([p for p in signature(p).parameters.values()
                if p.kind in {p.POSITIONAL_ONLY,
                              p.POSITIONAL_OR_KEYWORD,
                              p.VAR_POSITIONAL}])

def convert(p: Parameter, value: str) -> Any:
    if value == p.empty:
        return p.default
    t = p.annotation
    if type(t) is type:
        with suppress(Exception):
            return t(value)
    if t == Path or t == Union[Path, str]:
        return Path(value)
    if callable(t):
        with suppress(Exception):
            return t(value)
    return value

_no_flags = {}
def command(
    cmd: Optional[Callable] = None,
    flags: KeywordInputSpecs = _no_flags,
    for_value: bool = False,
    alias: Optional[str] = None,
    export: bool = False,
    prefix: Optional[tuple[PrefixCommandInvoker, str]]=None,
    _export=_export,
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
        def command_(cmd):
            return command(
                cmd,
                flags=flags,
                for_value=for_value,
                export=export,
                prefix=prefix,
            )
        return command_
    if alias is None:
        alias = cmd.__name__.replace("_", "-")

    invoker: CommandInvoker = CommandInvoker(cmd, alias,
                                            for_value=for_value,
                                            flags=flags,
                                            export=_export,
                                            )

    if prefix is not None:
        prefix_cmd, prefix_alias = prefix
        prefix_cmd.add_subcommand(prefix_alias, invoker) # type: ignore
    return invoker

def prefix_command(alias: str):
    """
    Create a command that invokes other commands selected by prefix.
    """
    prefix_cmd = PrefixCommandInvoker(lambda: None, alias,
                                      export=_export)

    @contextual_completer
    def completer(ctx: CompletionContext):
        if (
            ctx.command
            and ctx.command.prefix.strip() == alias
        ):
                return set(prefix_cmd.subcommands.keys())
        return set()
    completer.__doc__ = f"Completer for {alias}"
    def init_prefix_command(xsh: XonshSession):
        add_one_completer(alias, completer, "start")
        prefix_cmd.inject(XSH=xsh, XGIT=context(xsh))
    return prefix_cmd

xgit = prefix_command("xgit")
