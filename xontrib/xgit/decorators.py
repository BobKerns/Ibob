"""
Various decorators for xgit commands and functions.

"""

from contextlib import suppress
from functools import wraps
from typing import (
    Any, MutableMapping, NamedTuple, Optional, Callable, Union,
    cast, TypeVar, ParamSpec, Sequence
)
from inspect import signature, Signature, Parameter
from pathlib import Path
from weakref import WeakKeyDictionary

from xonsh.completers.tools import (
    contextual_completer, ContextualCompleter, CompletionContext,
)
from xonsh.completers.completer import add_one_completer
from xonsh.completers.path import (
    complete_path,
    complete_dir as _complete_dir,
    _complete_path_raw
)
from xonsh.built_ins import XonshSession, XSH as GLOBAL_XSH
from xonsh.events import events

from xontrib.xgit.types import (
    LoadAction, CleanupAction, GitError, ObjectId,
    Directory, File, PythonFile,
)
from xontrib.xgit.ref_types import (
    Branch, Tag, RemoteBranch, GitRef,
)
from xontrib.xgit.context import GitContext, _GitContext
from xontrib.xgit.invoker import CommandInvoker, PrefixCommandInvoker, SessionInvoker


_load_actions: list[LoadAction] = []

_unload_actions: WeakKeyDictionary[XonshSession, list[CleanupAction]] = WeakKeyDictionary()
"""
Actions to take when unloading the module.
"""

def _do_load_actions(xsh: XonshSession):
    """
    Load values supplied by the xontrib.
    """
    global _load_actions
    if not isinstance(_load_actions, list):
        return
    while _load_actions:
        _do_load_action(_load_actions.pop(), xsh)

def _do_load_action(action: LoadAction, xsh: XonshSession):
        try:
            unloader = action(xsh)
            if unloader is not None:
                _add_unload_action(xsh, unloader)
        except Exception:
            from traceback import print_exc
            print_exc()

def _add_load_action(action: LoadAction):
    """
    Add an action to take when loading the xontrib.
    """
    _load_actions.append(action)

def _add_unload_action(xsh: XonshSession, action: CleanupAction):
    """
    Add an action to take when unloading the xontrib.
    """
    default: list[CleanupAction] = []
    unloaders = _unload_actions.get(xsh, default)
    if unloaders is default:
        _unload_actions[xsh] = unloaders
    unloaders.append(action)

def _do_unload_actions(xsh: XonshSession):
    """
    Unload a value supplied by the xontrib.
    """
    for action in _unload_actions[xsh]:
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

def context(xsh: Optional[XonshSession] = GLOBAL_XSH) -> GitContext:
    if xsh is None:
        raise GitError('No xonsh session supplied.')
    env = xsh.env
    if env is None:
        raise GitError('xonsh session has no env attribute.')
    XGIT = env.get('XGIT')
    if XGIT is None:
        XGIT = _GitContext(xsh)
        env['XGIT'] = XGIT
        def unload_context():
            del env['XGIT']
        _add_unload_action(xsh, unload_context)
    return cast(GitContext, XGIT)

F = TypeVar('F', bound=Callable)
T =  TypeVar('T')
P = ParamSpec('P')
def session(
    event_name: Optional[str] = None,
    ):
    '''
    Decorator to bind functions such as event handlers to a session.

    They receive the session and context as as the keyword arguments:
    XSH=xsh, XGIT=context

    When the plugin is unloaded, the functions are turned into no-ops.
    '''
    def decorator(func: Callable[P,T]) -> Callable[...,T]:
        wrapper = SessionInvoker(func)
        def loader(xsh: XonshSession):
            wrapper.inject(XSH=xsh, XGIT=context(xsh))
            if event_name is not None:
                ev = getattr(events, event_name)
                ev(wrapper)
            else:
                ev = None
            def unload():
                if ev is not None:
                    ev.remove(wrapper)
                wrapper.uninject()
            return unload
        _add_load_action(loader)
        return cast(Callable[...,T], wrapper)
    return decorator

@contextual_completer
@session()
def complete_hash(context: CompletionContext, *, XGIT: GitContext) -> set:
    return set(XGIT.objects.keys())

@session()
def complete_ref(prefix: str = "", *, XGIT: GitContext) -> ContextualCompleter:
    '''
    Returns a completer for git references.
    '''
    @contextual_completer
    def completer(context: CompletionContext) -> set[str]:
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
    # Below only in test hardness
    _aliases = {}
    _exports = []

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
                if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL}])

def convert(p: Parameter, value: str) -> Any:
    if value == p.empty:
        return p.default
    t = p.annotation
    if type(t) == type:
        with suppress(Exception):
            return t(value)
    if t == Path or t == Union[Path, str]:
        return Path(value)
    if callable(t):
        with suppress(Exception):
            return t(value)
    return value

def command(
    cmd: Optional[Callable] = None,
    flags: set = set(),
    for_value: bool = False,
    alias: Optional[str] = None,
    export: bool = False,
    prefix: Optional[tuple[PrefixCommandInvoker, str]]=None,
    _export=_export,
    _aliases=_aliases,
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
                alias=alias,
                export=export,
                prefix=prefix,
            )
        return command_
    if alias is None:
        alias = cmd.__name__.replace("_", "-")

    invoker: CommandInvoker = CommandInvoker(cmd, alias)
    def loader(xsh: XonshSession):
        invoker.inject(XSH=xsh, XGIT=context(xsh))
        return invoker.uninject
    _add_load_action(loader)

    _aliases[alias] = invoker.command
    if export:
        _export(cmd)
    if prefix is not None:
        prefix_cmd, prefix_alias = prefix
        prefix_cmd.add_subcommand(prefix_alias, invoker) # type: ignore
    return invoker

def prefix_command(alias: str):
    """
    Create a command that invokes other commands selected by prefix.
    """
    prefix_cmd = PrefixCommandInvoker(lambda: None, alias)
    _aliases[alias] = prefix_cmd
    @contextual_completer
    def completer(ctx: CompletionContext):
        if ctx.command:
            if ctx.command.prefix.strip() == alias:
                return set(prefix_cmd.subcommands.keys())
        return set()
    completer.__doc__ = f"Completer for {alias}"
    def init_prefix_command(xsh: XonshSession):
        add_one_completer(alias, completer, "start")
        prefix_cmd.inject(XSH=xsh, XGIT=context(xsh))
    return prefix_cmd

xgit = prefix_command("xgit")
