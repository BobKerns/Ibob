"""
Various decorators for xgit commands and functions.

"""

from contextlib import suppress
from functools import wraps
from typing import (
    Any, MutableMapping, NamedTuple, Optional, Callable, Union,
    TypeAlias, cast, TypeVar, ParamSpec,
)
from inspect import signature, Signature, Parameter
import sys
from pathlib import Path

from xonsh.completers.tools import (
    contextual_completer, ContextualCompleter, CompletionContext,
)
from xonsh.completers.completer import add_one_completer
from xonsh.completers.path import (
    complete_path,
    complete_dir as _complete_dir,
    _complete_path_raw
)
from xonsh.parsers.completion_context import CompletionContext
from xonsh.built_ins import XonshSession
from xonsh.events import events

from xontrib.xgit.types import (
    LoadAction, CleanupAction, GitError, GitHash,
    Directory, File, PythonFile,
)
from xontrib.xgit.ref_types import (
    Branch, Tag, RemoteBranch, GitRef,
)
from xontrib.xgit.context import GitContext, _GitContext

_load_actions: list[LoadAction]|XonshSession = []

_unload_actions: list[CleanupAction] = []
"""
Actions to take when unloading the module.
"""
def _do_load_actions(xsh: XonshSession):
    """
    Load a value supplied by the xontrib.
    """
    global _load_actions
    if not isinstance(_load_actions, list):
        return
    while _load_actions:
        _do_load_action(_load_actions.pop(), xsh)
    # All done, clear the list so no more actions are added.
    # They should be run immediately now.
    _load_actions = xsh

def _do_load_action(action: LoadAction, xsh: XonshSession):
        try:
            unloader = action(xsh)
            if unloader is not None:
                _unload_actions.append(unloader)
        except Exception:
            from traceback import print_exc
            print_exc()

def _add_load_action(action: LoadAction, xsh: XonshSession|None):
    """
    Add an action to take when loading the xontrib.
    """
    if isinstance(_load_actions, list):
        _load_actions.append(action)
    else:
        _do_load_action(action, _load_actions)

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

def context(xsh: Optional[XonshSession] = None) -> GitContext:
    if xsh is None:
        raise GitError('No xonsh session supplied.')
    if xsh.env is None:
        raise GitError('xonsh session has no env attribute.')
    XGIT = xsh.env.get('XGIT')
    if XGIT is None:
        XGIT = _GitContext(xsh)
        xsh.env['XGIT'] = XGIT
    return cast(GitContext, XGIT)

F = TypeVar('F', bound=Callable)
T =  TypeVar('T')
P = ParamSpec('P')
def session(event_name: Optional[str] = None):
    '''
    Decorator to bind functions such as event handlers to a session.

    They receive the session and context as as the keyword arguments:
    XSH=xsh, XGIT=context

    When the plugin is unloaded, the functions are turned into no-ops.
    '''
    def decorator(func: Callable[P,T]) -> Callable[...,T]:
        active = True
        last_return = None
        XSH: XonshSession|None = None
        XGIT: GitContext|None = None
        def loader(xsh: XonshSession):
            nonlocal XSH, XGIT
            XSH = xsh
            XGIT = context(xsh)
            def unloader():
                nonlocal active, XSH, XGIT
                active = False
                XGIT = None
                if XSH is not None:
                    env = XSH.env
                    if env is not None:
                        with suppress(KeyError):
                            del env['XGIT']
                    XSH = None
            return unloader

        @wraps(func)
        def wrapper(*args, XSH: XonshSession, XGIT: GitContext, **kwargs):
            t_func = cast(Callable, func)
            nonlocal last_return
            if active:
                last_return = t_func(*args,
                                   XSH=XSH,
                                   XGIT=context(XSH),
                                   **kwargs)
            return last_return

        def rewrap(*args, **kwargs):
            if XSH is None:
                raise GitError('No xonsh session')
            if XGIT is None:
                raise GitError('No git context')
            return wrapper(*args, XSH=XSH, XGIT=XGIT, **kwargs)

        _add_load_action(loader, XSH)
        rewrap.__doc__ = func.__doc__
        rewrap.__name__ = func.__name__
        rewrap.__qualname__ = func.__qualname__ + '_session'
        rewrap.__module__ = func.__module__
        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        wrapper.__qualname__ = func.__qualname__ + '_session_inner'
        wrapper.__module__ = func.__module__
        return cast(Callable[...,T], rewrap)
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
    wrapper: Callable
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
    args: list
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
    prefix: Optional[tuple[Callable[..., Any], str]]=None,
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
        return lambda cmd: command(
            cmd,
            flags=flags,
            for_value=for_value,
            alias=alias,
            export=export,
            prefix=prefix,
        )
    if alias is None:
        alias = cmd.__name__.replace("_", "-")

    sig: Signature = signature(cmd)
    @session()
    def wrapper(
        xargs,
        /, *,
        XSH: XonshSession,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        **kwargs,
    ):
        if "--help" in xargs:
            print(getattr(cmd, "__doc__", ""), file=stderr)
            return
        args: list[str] = [*xargs]
        p_args: list[str] = []
        while len(args) > 0:
            if args[0] == "--":
                args.pop(0)
                continue
            if args[0].startswith("--"):
                if "=" in args[0]:
                    k, v = args.pop(0).split("=", 1)
                    kwargs[k[2:]] = v
                else:
                    if args[0] in flags or args[0][2:] in flags:
                        kwargs[args.pop(0)[2:]] = True
                    else:
                        kwargs[args.pop(0)[2:]] = args.pop(0)
            else:
                p_args.append(args.pop(0))

        n_args = []
        n_kwargs = {}
        env = XSH.env
        assert isinstance(env, MutableMapping),\
            f"XSH.env not a MutableMapping: {env!r}"

        info = InvocationInfo(
            cmd=cmd.info, # type: ignore
            args=args,
            kwargs=kwargs,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
        )

        kwargs = {
            "_info": info,
            **kwargs
        }

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
                        value = convert(p, value)
                        n_args.append(value)

                    case p.POSITIONAL_OR_KEYWORD:
                        positional = len(p_args) > 0
                        if value == p.empty:
                            if positional:
                                value = p_args.pop(0)
                            elif p.name in kwargs:
                                value = kwargs.pop(p.name)
                            else:
                                value = p.default
                        if value == p.empty:
                            raise ValueError(f"Missing value for {p.name}")  # noqa

                        value = convert(p, value)
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
                        value = convert(p, value)
                        n_kwargs[p.name] = value
                    case p.VAR_POSITIONAL:
                        if len(p_args) > 0:
                            n_args.extend(p_args)
                            p_args.clear()
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
    wrapper.__qualname__ = cmd.__qualname__ + '_command'
    wrapper.__doc__ = cmd.__doc__
    wrapper.__module__ = cmd.__module__
    _aliases[alias] = wrapper
    if export:
        _export(cmd)
    if prefix is not None:
        prefix_cmd, prefix_alias = prefix
        prefix_cmd._subcmds[prefix_alias] = wrapper # type: ignore
    cmd.info =  CommandInfo(cmd, wrapper, alias, sig)   # type: ignore
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
        return subcmds[subcmd](args, **kwargs)
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
        if ctx.command:
            if ctx.command.prefix.strip() == alias:
                return set(subcmds.keys())
        return set()
    completer.__doc__ = f"Completer for {alias}"
    add_one_completer(prefix_name, completer, "start")
    return prefix_cmd

xgit = prefix_command("xgit")
