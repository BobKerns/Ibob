'''
Utilities for invoking commands based on their signatures.
'''

from abc import abstractmethod
from collections.abc import Sequence
from itertools import chain
import sys
from types import MappingProxyType
from typing import (
    IO, Any, Callable, Generic, Literal, NamedTuple, Optional, TypeVar,
)
from collections.abc import MutableMapping
from inspect import Parameter, Signature

from xonsh.built_ins import XonshSession
from xonsh.events import Event, events
from xonsh.completers.tools import (
    CompletionContext,
)

from xontrib.xgit.types import (
    GitValueError, KeywordSpec, KeywordSpecs,
    KeywordInputSpec, KeywordInputSpecs,
    list_of,
)
from xontrib.xgit.conversion_mgr import ArgTransform
import xontrib.xgit.runners as run

class ArgSplit(NamedTuple):
    """
    A named tuple that represents a split of arguments and keyword arguments.

    """
    args: list[Any]
    '''
    The arguments to be matched positionally.
    '''
    extra_args: list[Any]
    kwargs: dict[str, Any]
    extra_kwargs: dict[str, Any]

class ArgumentError(GitValueError):
    '''
    An error that occurs when an argument is invalid.
    '''
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

def _u(s: str) -> str:
    return s.replace('-', '_')

def _h(s: str) -> str:
    return s.replace('_', '-')

class Invoker:
    __name__: str
    @property
    def name(self) -> str:
        return self.__name__

    __function: Callable
    @property
    def function(self) -> Callable:
        '''
        The function that is invoked by the invoker.
        '''
        return self.__function

    def __init__(self, cmd: Callable, name: Optional[str] = None, /,):
        if not callable(cmd):
            raise ValueError(f"An Invoker must wrap a callable function: {cmd!r}")
        self.__function = cmd
        # Be a proper wrapper
        self.__name__ = name or _h(cmd.__name__)
        self.__qualname__ = cmd.__qualname__
        self.__doc__ = cmd.__doc__ or self.__doc__ or ''
        self.__module__ = cmd.__module__
        self.__annotations__ = cmd.__annotations__

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.
        """
        __tracebackhide__ = True
        try:
            return self.__function(*args, **kwargs)
        except TypeError as e:
            if (
                e.__traceback__ and
                e.__traceback__.tb_frame.f_locals.get('self') is self
            ):
                raise ArgumentError(str(e)) from None
            raise


    _signature: Signature|None = None
    __signature__: Signature
    @property
    def signature(self) -> Signature:
        """
        The signature of the command to be invoked.

        """
        if self._signature is None:
            self._signature = Signature.from_callable(self.function)
            self.__signature__ = self._signature
        return self._signature

    __runner_signature: Signature|None = None
    @property
    def runner_signature(self) -> Signature:
        '''
        The signature of the runner that is created by the invoker.
        '''
        if self.__runner_signature is None:
            self.__runner_signature = self._runner_signature()
        return self.__runner_signature


    def _runner_signature(self) -> Signature:
        '''
        Compute the `Signature` of the `Runner` that is created by the `Invoker`.

        The default is to use the `Invoker`'s signature, but this can be overridden.
        '''
        return self.signature


    def __repr__(self) -> str:
        return f'<{type(self).__name__}({self.name})(...)>'

R = TypeVar('R', bound=run.BaseSessionRunner)

class BaseSessionInvoker(Generic[R], Invoker):
    '''
    An invoker that handles creating runners with session variables. This divides
    into two types: `RunnerPerSessionInvoker` and `SharedSessionInvoker`.

    `RunnerPerSessionInvoker` creates a new runner for each session, and registers
    it within the session. This is the preferred protocol, where there is not an
    exclusive value for a global variable, such as `sys.displayhook`.displayhook

    The alternative, `SharedSessionInvoker`, creates a single runner that is shared
    in all sessions. It retrieves the session variables from from inspecting its
    context. This typically involves searching up the stack to find the session
    variables.
    '''

    @abstractmethod
    def create_runner(self, /, **kwargs) -> R:
        '''
        Creates a `Runner` for this `Invoker`.
        '''
        ...


    @abstractmethod
    def _perform_injections(self, runner: R, /, **session_vars: Any):
        '''
        Injects session variables into the `Runner`. In subclasses where the
        `Invoker` is notified of the session variables, this method should be
        overridden to perform the injections.

        In subclasses where the `Runner` is shared (cannot be per-session),
        the `Runner` is responsible for discovering the session variables,
        and this method should do nothing.

        PARAMETERS
        ----------
        runner: run.Runner
            The runner to be injected.
        session_vars: dict[str, Any]
            The session variables to be injected.
        '''
        ...


    def __call__(self, /, *args: Any,
                stdout: Optional[IO[str]]=None,
                stderr: Optional[IO[str]]=None,
                stdin: Optional[IO[str]]=None,
                **kwargs: Any) -> Any:
        '''
        Invokes the function with the given arguments and keyword arguments.

        We supply `stdin`, `stdout`, and `stderr` as keyword arguments, if the
        underlying function accepts them explicitly.

        '''
        __tracebackhide__ = True

        params = self.signature.parameters
        if 'stdout' in params:
            kwargs['stdout'] = stdout or sys.stdout
        if 'stderr' in params:
            kwargs['stderr'] = stderr or sys.stderr
        if 'stdin' in params:
            kwargs['stdin'] = stdin or sys.stdin

        return super().__call__(*args, **kwargs)

    def _register_invoker(self, *args, **kwargs):
        '''
        Registers to be notified of the session.

        Default is to do nothing, to simplify test fixtures.
        '''
        pass

    def _register_runner(self, runner: R, /, **session_vars: Any):
        '''
        Registers the `Runner` with the session.

        Default is to do nothing, to simplify test fixtures.
        '''
        pass
class SharedSessionInvoker(BaseSessionInvoker[run.SharedSessionRunner]):
    '''
    An invoker that handles creating runners with session variables.
    '''

    @abstractmethod
    def create_runner(self, /, **kwargs) -> run.SharedSessionRunner:
        '''
        Creates a runner for this `Invoker`.

        PARAMETERS
        ----------
        kwargs: dict[str, Any]
            `Invoker`-specific keyword arguments.
        '''
        return run.SharedSessionRunner(self, **kwargs)


    def _perform_injections(self, runner: run.Runner, /, **session_vars: Any):
        '''
        In `SharedSessionInvoker`, the `Runner` is responsible for discovering
        the session variables on the fly, so this method should do nothing.

        PARAMETERS
        ----------
        runner: run.Runner
            The runner to be injected.
        session_vars: dict[str, Any]
            The session variables to be injected.
        '''
        pass

RPSR = TypeVar('RPSR', bound=run.RunnerPerSessionRunner)
class RunnerPerSessionInvoker(BaseSessionInvoker[RPSR]):
    '''
    An invoker that creates a new runner for each session.
    '''

    def __init__(self, cmd: Callable, name: Optional[str] = None, /, ** kwargs):
        super().__init__(cmd, name, **kwargs)
        self._register_invoker()


    def inject(self, /, **session_vars: Any):
        '''
        Injects session variables into the `Invoker`.  In subclasses of
        `RunnerPerSessionInvoker`, this method this method creates a new
        `Runner` for each session, and injects the session variables into
        `Runner`.
        '''
        runner = self.create_runner(invoker=self,
                                    name=self.name,
                                    **session_vars)
        self._perform_injections(runner, **session_vars)
        self._register_runner(runner, **session_vars)


    def _perform_injections(self, runner: RPSR, /,
                            **session_vars: Any):
        '''
        Injects session variables into the `Runner`. By default, this is
        delegated to the `Runner` itself.
        '''
        runner.inject(**session_vars)


    @abstractmethod
    def _register_invoker(self, *args, **kwargs):
        '''
        Registers to be notified of the session
        '''
        # Pytest fails setting a verify attribute on a bound method, so use
        # a real function.
        def on_load(**session_args):
            self.inject(**session_args)
        events.on_xgit_load(on_load)


    @abstractmethod
    def _register_runner(self, runner: RPSR, /, **session_vars: Any):
        '''
        Registers the `Runner` with the session.
        '''
        ...


class EventInvoker(RunnerPerSessionInvoker[run.EventRunner]):
    __event: Event
    @property
    def event(self) -> Event:
        '''
        The event that the invoker registers with.
        '''
        return self.__event

    def create_runner(self, /, **kwargs) -> run.EventRunner:
        return run.EventRunner(self, event=self.event, **kwargs)

    def _perform_injections(self, runner: run.EventRunner, /, **session_vars: Any):
        return super()._perform_injections(runner, **session_vars)

    def _register_runner(self, runner: run.EventRunner, /, **session_vars: Any):
        self.__event(runner)

    def __init__(self, event: Event, cmd: Callable,
                    name: Optional[str] = None, /,
                    **kwargs):
        self.__event = event
        super().__init__(cmd, name,  **kwargs)


class CommandInvoker(RunnerPerSessionInvoker):
    '''
    An invoker that can handle more complex argument parsing that
    involves type checking, name-matching, and conversion.
    '''
    __arg_transforms: dict[str, ArgTransform]
    @property
    def arg_transforms(self) -> dict[str, ArgTransform]:
        '''
        The transformations that are applied to the arguments.
        '''
        return self.__arg_transforms

    __export: Callable[[Any,str|None],None]|None
    @property
    def export(self) -> Callable[[Any,str|None],None]|None:
        '''
        The function that is used to export the invoker.
        '''
        return self.__export

    __for_value: bool
    @property
    def for_value(self) -> bool:
        '''
        Whether the invoker is used to return a value.
        '''
        return self.__for_value


    def __init__(self, cmd: Callable,
                 name: Optional[str] = None, /, *,
                 export: Optional[Callable[[Any,str|None],None]] = None,
                 flags: Optional[KeywordInputSpecs] = None,
                 for_value: bool = False,
                 **kwargs):
        super().__init__(cmd, name, **kwargs)
        self.__arg_transforms = {}
        self.__for_value = for_value
        self.__export = export

        if flags is None:
            flags = {}
        def flag_tuple(k: str, v: str|KeywordInputSpec) -> KeywordSpec:
            match v:
                case '*' | '+' | 0 | 1 | bool():
                    return v, k
                case str():
                    return True, _u(v)
                case (0|1|bool()|'+'|'*'), str():
                    return v
                case _:
                    raise ValueError(f"Invalid flag value: {v!r}")
        self.__flags = {k:flag_tuple(k, s) for k, s in  flags.items()}
        self.__flags_with_signature = None


    __flags: KeywordSpecs
    __flags_with_signature: KeywordSpecs|None = None
    @property
    def flags(self) -> KeywordSpecs:
        """
        A set of flags that are recognized by the invoker. Flags are keywords
        without supplied values; they are either present (`True`) or absent
        (`False`). This can be inverted with the use of `--no-` prefixes.

        Thus, to supply an explicit `False` value for a flag `my-flag`,
        use the `--no-my-flag` argument.

        Each spec is a tuple of the flag name, the number of arguments it takes,
        and the keyword argument to be matched in the function.

        If the number of arguments is zero, the flag is treated as
        a boolean flag, and the flag itself is supplied as an argument.

        If the number of arguments is specified as a boolean that
        value is used, unless negated with the `--no-` prefix.


        - `True`: Zero argument boolean flag, `True` if supplied
        - `False`: Zero argument boolean flag, `False` if supplied
        - `0`: Zero argument keyword, the flag name if supplied
        - `1`: One argument follows the keyword.
        - `+`: One or more arguments follow the keyword.
        - `*`: Zero or more arguments follow the keyword.
        """
        if (v := self.__flags_with_signature) is not None:
            return v
        flags = self.__flags
        sig = self.signature
        for p in sig.parameters.values():
            if p.name in flags:
                continue
            match p.kind, p.annotation:
                case _, cls if isinstance(cls, type) and issubclass(cls, bool):
                    flags[_h(p.name)] = (True, p.name)
                case p.POSITIONAL_ONLY, _:
                    continue
                case p.POSITIONAL_OR_KEYWORD, _:
                    flags[_h(p.name)] = (1, p.name)
                case p.VAR_POSITIONAL, _:
                    flags[_h(p.name)] = ('*', p.name)
                case p.KEYWORD_ONLY, _:
                    flags[_h(p.name)] = (1, p.name)
                case p.VAR_KEYWORD, _:
                    continue
                case _:
                    continue
        self.__flags_with_signature = flags
        return flags



    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments,
        parsed and repackaged according to the command's signature.

        """
        __tracebackhide__ = True
        split = self.extract_keywords(args)
        unified_kwargs = {**split.kwargs, **split.extra_kwargs, **kwargs}
        return super().__call__(*split.args, **unified_kwargs)


    def _perform_injections(self, runner: run.Runner, /, *,
                            XSH: XonshSession,
                            **session_vars: Any):
        '''
        Injects session variables into the runner.
        '''
        ctx = XSH.ctx

        for_value = self.__for_value
        def value_handler(result: Any):
            if for_value:
                ctx['$'] = result
            # Suppress xonsh's default output.
            return (None, None, 0, result)

        sig = self.signature
        # Copy so we can modify while iterating.
        s_vars = dict(session_vars, XSH=XSH)
        for key in session_vars:
            if key not in sig.parameters:
                s_vars.pop(key, None)
        runner.inject(value_handler=value_handler, **s_vars)

    def _register_runner(self, runner: run.Runner, /, *,
                        XSH: XonshSession,
                        **session_vars: Any):
        '''
        Registers the `Runner` (`Command`) with the session:
        * Adds the `Command` to the aliases.
        * Adds the `Command` to the unload event.
        * Calls the export function to export the `Command` function into the
          session.
        '''
        aliases = XSH.aliases
        assert isinstance(aliases, MutableMapping)
        aliases[self.name] = runner

        unexport: Callable|None = None
        export = self.__export
        if export is not None:
            export(self, self.function.__name__)
        def on_unload(**kwargs):
            aliases.pop(self.name, None)
            if unexport is not None:
                unexport()
            runner.uninject()
        events.on_xgit_unload(on_unload)

    def _runner_signature(self) -> Signature:
        '''
        The signature of the `Runner` that is created by the `Invoker`.

        For commands, the `Runner` signature is quite different from the `Invoker`.
        We do our best to capture the `Command`'s signature, including the parsed
        string arguments and the session variables.
        '''
        sig: Signature = self.signature
        params = [
            p.annotation|str for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.VAR_KEYWORD)
        ]
        keywords = [
            t for ts in (
                (Literal[f'--{p.name}'], p.annotation)
                for p in sig.parameters.values()
                if p.kind is p.KEYWORD_ONLY
            )
            for t in ts
        ]
        session_keywords = [
            p for p in sig.parameters.values()
            if p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD)
        ]

        params = tuple(chain(keywords, params))
        # list_of is a workaround python 3.10.
        args = Parameter('args', Parameter.POSITIONAL_ONLY,
                         annotation=list_of(params))

        return Signature([args, *session_keywords],
                        return_annotation=sig.return_annotation)

    def create_runner(self, /,
               **kwargs) -> run.Command:
        '''
        Creates a runner with the given session variables.

        PARAMETERS
        ----------
        _export: Callable[[Any,str|None],None]
            The function that is used to export the invoker.
        '''
        return run.Command(self,
                            export=self.export,
                           **kwargs)

    def extract_keywords(self, arglist: Sequence[Any]) -> ArgSplit:
        """
        The first phase of the command invocation involves parsing the command-line
        arguments into positional and keyword arguments according to normal command-line
        conventions.

        To do this, we need to know the flags that are recognized by the commands,
        and how they are to be interpreted.  We can make good guesses based on
        our knowledge of the command's signature, but we allow explicit specification
        of flags to override and augment our guesses.

        This function extracts keyword arguments from a list of command-line arguments.

        It is permitted to pass non-string arguments, as either positional values
        or arguments to keyword parameters.

        This function's job is to separate the positional arguments from the
        definite keyword arguments.

        These positional arguments may turn out to match keywords by name in a
        later phase, based on the command's signature.

        """
        s = ArgSplit([], [], {}, {})
        flags = self.flags
        if not arglist:
            return s
        args: list[Any] = list(arglist)
        def consume_kw_args(arg, n: KeywordSpec, /, *,
                            to: dict[str, Any] = s.kwargs,
                         negate: bool = False):
            match *n, negate:
                case bool(b), str(k), False:
                    to[k] = b
                case bool(b), str(k), True:
                    to[k] = not b
                case 0, str(k), _:
                    to[k] = arg
                case 1, str(k), False:
                    to[k] = args.pop(0)
                case '+', str(k), False:
                    if len(args) == 0:
                        raise ArgumentError(f"Missing argument for {arg}")
                    argl1 = [args.pop(0)]
                    while (
                        args
                        and not (isinstance(args[0], str) and args[0].startswith("-"))
                    ):
                       argl1.append(args.pop(0))
                    to[k] = argl1
                case '*', str(k), False:
                    argl2 = []
                    while (
                        args
                        and not (isinstance(args[0], str) and args[0].startswith("-"))
                    ):
                        argl2.append(args.pop(0))
                    to[k] = argl2
                case _:
                    raise ValueError(f"Invalid flag usage: {arg} {n!r}")
        while args:
            arg = args.pop(0)
            if isinstance(arg, str):
                if arg == '-':
                    s.args.append(arg)
                elif arg == '--':
                    s.extra_args.extend(args)
                    args = []
                elif arg.startswith("--"):
                    if "=" in arg:
                        k, v = arg[2:].split("=", 1)
                        args.insert(0, v)
                        if (n := flags.get(k)) is not None:
                            consume_kw_args(k, n)
                        else:
                            consume_kw_args(k, (1, k), to=s.extra_kwargs)
                    else:
                        if (
                            arg.startswith("--no-")
                            and ((n := flags.get(key := arg[5:])) is not None)
                        ):
                            consume_kw_args(arg, n, negate=True)
                        elif ((n:= flags.get(key := arg[2:])) is not None):
                            consume_kw_args(key, n)
                        elif arg.startswith("--no-"):
                            s.extra_kwargs[_u(arg[5:])] = False
                        else:
                            s.extra_kwargs[_u(arg[2:])] = True
                elif arg.startswith("-"):
                    arg = arg[1:]
                    for c in arg:
                        if (n := flags.get(c)) is not None:
                            consume_kw_args(arg, n)
                        else:
                            s.extra_kwargs[c] = True
                else:
                    s.args.append(arg)
            else:
                s.args.append(arg)
        return s


class PrefixCommandInvoker(CommandInvoker):
    '''
    An invoker that can handle more complex argument parsing that
    involves type checking, name-matching, and conversion.
    '''

    __prefix: str
    @property
    def prefix(self) -> str:
        '''
        The prefix that is used to invoke the command.
        '''
        return self.__prefix

    __subcommands: dict[str, CommandInvoker]
    @property
    def subcommands(self) -> MappingProxyType[str, CommandInvoker]:
        '''
        The subcommands that are recognized by the invoker.
        '''
        return MappingProxyType(self.__subcommands)

    def add_subcommand(self, subcmd: str, invoker: CommandInvoker):
        '''
        Adds a subcommand to the invoker.

        PARAMETERS
        ----------
        subcmd: str
            The name of the subcommand.
        invoker: CommandInvoker
            The invoker that is used to invoke the subcommand.
        '''
        self.__subcommands[subcmd] = invoker
        @property
        def subcommands(self) -> MappingProxyType[str, CommandInvoker]:
            return MappingProxyType(self.__subcommands)

    def create_runner(self, /,
                    **kwargs) -> run.PrefixCommand:
        '''
        Creates a `PrefixCommand` runner, and all its subcommands.
        '''
        def create_and_inject(invoker: CommandInvoker):
            runner = invoker.create_runner(**kwargs)
            invoker._perform_injections(runner, **kwargs)
            # But don't register this runner
            return runner

        subcommands = {
            k: create_and_inject(invoker)
            for k, invoker in self.subcommands.items()
        }

        return run.PrefixCommand(self,
                                 subcommands=subcommands,
                                 **kwargs)

    def _complete_subcommands(self, ctx: CompletionContext) -> set[str]:
        '''
        Completes the subcommands that match the given prefix.

        PARAMETERS
        ----------
        prefix: str
            The prefix to be matched.

        RETURNS
        -------
        list[str]
            The subcommands that match the prefix.
        '''
        if (cmd_ctx := ctx.command) is None:
            return set()
        prefix = cmd_ctx.prefix
        if self.prefix.startswith(prefix):
            return {self.prefix}
        return {f'{self.prefix} {k}' for k in self.subcommands}

    def __init__(self,
                 cmd: Callable, /,
                 prefix: str,
                 flags: Optional[KeywordInputSpecs] = None,
                 **kwargs):
        self.__prefix = prefix
        self.__subcommands = {}
        super().__init__(cmd, prefix,
                         flags=flags,
                         **kwargs)


    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True
        if len(args) == 0:
            for subcmd in self.subcommands:
                print(f'  {subcmd}', file=sys.stderr)
                return
        else:
            subcmd_name = args[0]
            if subcmd_name not in self.subcommands:
                raise GitValueError(f"Invalid subcommand: {subcmd_name}")
            subcmd = self.subcommands[subcmd_name]
            return subcmd(*args[1:], **kwargs)