'''
Utilities for invoking commands based on their signatures.
'''

from collections.abc import Sequence
from contextlib import suppress
from itertools import chain
import sys
from types import MappingProxyType
from typing import (
    IO, Any, Callable, Literal, NamedTuple, Optional,
)
from inspect import Parameter, Signature

from xonsh.events import events
from xonsh.completers.tools import (
    contextual_completer, ContextualCompleter, CompletionContext,
)
from xonsh.completers.completer import add_one_completer

from xontrib.xgit.types import (
    GitNoSessionException, GitValueError, KeywordSpec, KeywordSpecs,
    KeywordInputSpec, KeywordInputSpec, KeywordInputSpecs,
    list_of,
)

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

class ArgumentError(ValueError):
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

class BaseInvoker:
    __name__: str
    __function: Callable
    @property
    def function(self) -> Callable:
        return self.__function

    def __init__(self, cmd: Callable):
        if not callable(cmd):
            raise ValueError(f"Command must be callable: {cmd!r}")
        self.__function = cmd
        # Be a proper wrapper
        self.__name__ = cmd.__name__
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
            if e.__traceback__ and e.__traceback__.tb_frame.f_locals.get('self') is self:
                raise ArgumentError(str(e)) from None
            raise

    def __repr__(self) -> str:
        return f'<{type(self).__name__}({self.__name__})(...)>'

class SimpleInvoker(BaseInvoker):
    """
    Invokes commands based on normal conventions.
    """

    __flags: KeywordSpecs
    @property
    def flags(self) -> KeywordSpecs:
        '''
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
        '''
        return self.__flags

    '''
    The function to be invoked.
    '''

    def __init__(self,
                 cmd: Callable,
                 flags: Optional[KeywordInputSpecs] = None,
                 ):
        '''
        Initializes the invoker with the given command and flags.

        PARAMETERS
        ----------
        cmd: Callable
            The command to be invoked.
        flags: Optional[KeywordInputSpecs]
            The flags that are recognized by the invoker.
        '''
        super().__init__(cmd)
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


    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        __tracebackhide__ = True
        split = self.extract_keywords(args)
        unified_kwargs = {**split.kwargs, **split.extra_kwargs, **kwargs}
        return super().__call__(*split.args, **unified_kwargs)

    def extract_keywords(self, arglist: Sequence[Any]) -> ArgSplit:
        """
        The first phase of invocation involves parsing the command-line arguments
        into positional and keyword arguments according to normal conventions.

        To do thi, we need to know the flags that are recognized by the commands,
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
                    l = [args.pop(0)]
                    while args and not (isinstance(args[0], str) and args[0].startswith("-")):
                        l.append(args.pop(0))
                    to[k] = l
                case '*', str(k), False:
                    l = []
                    while args and not (isinstance(args[0], str) and args[0].startswith("-")):
                        l.append(args.pop(0))
                    to[k] = l
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
                        if arg.startswith("--no-") and ((n := flags.get(key := arg[5:])) is not None):
                            consume_kw_args(arg, n, negate=True)
                        elif ((n:= flags.get(key := arg[2:])) is not None):
                            consume_kw_args(arg, n)
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

class SignatureInvoker(SimpleInvoker):

    __signature: Signature|None = None
    @property
    def signature(self) -> Signature:
        """
        The signature of the command to be invoked.

        """
        if self.__signature is None:
            self.__signature = Signature.from_callable(self.function)
        return self.__signature

class Invoker(SignatureInvoker, SimpleInvoker):
    '''
    An invoker that can handle more complex argument parsing that
    involves type checking, name-matching, and conversion.
    '''

    __flags_with_signature: KeywordSpecs|None = None
    @property
    def flags(self) -> KeywordSpecs:
        """
        The flags that are recognized by the invoker.

        """
        if (v := self.__flags_with_signature) is not None:
            return v
        flags = dict(super().flags)
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

    def __init__(self,
                 cmd: Callable,
                 flags: Optional[KeywordInputSpecs] = None,
                 ):
        super().__init__(cmd, flags)
        self.__flags_with_signature = None


class SessionVariablesMixin(SignatureInvoker):
    '''
    A mixin that provides injected session variables to an invoker.
    '''

    __session_variables: dict[str, Any]|None
    @property
    def session_variables(self) -> dict[str, Any]:
        '''
        The session variables that are injected into the command.
        '''
        if self.__session_variables is None:
            raise GitNoSessionException(self.__name__)
        return self.__session_variables

    def inject(self, **kwargs):
        '''
        Injects session variables into the invoker.
        '''
        sig = self.signature
        if self.__session_variables is None:
            self.__session_variables = {}
        self.__session_variables.update(kwargs)

    def uninject(self, **kwargs):
        '''
        Removes all session variables from the invoker.
        '''
        self.__session_variables = None

    def __init__(self, cmd: Callable, flags: Optional[KeywordInputSpecs] = None, **kwargs):
        super().__init__(cmd, flags, **kwargs)
        self.__session_variables = None
        # Pytest doesn't seem to like bound methods here, so we'll wrap them.
        # (It looks for a validator attribute on the bound method, which is not there.
        # I don't know how or why it can even notice, but it does.)
        def on_load(*args, **kwargs):
            self.inject(**kwargs)
        def on_unload(*args, **kwargs):
            self.uninject(**kwargs)
        events.on_xgit_load(on_load)
        events.on_xgit_unload(on_unload)


    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.
        '''
        __tracebackhide__ = True
        params = self.signature.parameters
        for k, v in self.session_variables.items():
            if k in params:
                kwargs[k] = v

        return super().__call__(*args, **kwargs)

class Command:
    '''
    A command that can be invoked with the command-line calling sequence rather than
    the python one. This translates the command-line arguments (strings) into the
    appropriate types and injects session variables into the command.

    A proxy to an `Invoker` that can be called directly with command-line arguments.

    We could use the bound method directly, but that won't allow setting the signature.
    '''

    __invoker: 'CommandInvoker'
    @property
    def invoker(self) -> 'CommandInvoker':
        '''
        The invoker that is used to invoke the command.
        '''
        return self.__invoker

    __exclude: set[str]
    @property
    def exclude(self) -> set[str]:
        '''
        The names of the session variables that are excluded from the signature.
        '''
        return self.__exclude

    __signature__: Signature

    @property
    def signature(self) -> Signature:
        '''
        The signature of the command.

        '''
        if self.__signature__ is not None:
            return self.__signature__
        else:
            self.__signature__ = self._signature()
            return self.__signature__

    def _signature(self) -> Signature:
            sig = self.invoker.signature
            params = [
                p.annotation|str for p in sig.parameters.values()
                if p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.VAR_KEYWORD)
            ]
            keywords = [
                t for ts in (
                    (Literal[f'--{p.name}'], p.annotation)
                    for p in sig.parameters.values()
                    if p.kind is p.KEYWORD_ONLY
                    if p.name not in self.__exclude
                )
                for t in ts
            ]
            session_keywords = [
                p for p in sig.parameters.values()
                if (p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD)
                    or p.name in self.__exclude)
            ]

            params = tuple(chain(keywords, params))
            # list_of is a workaround python 3.10.
            args = Parameter('args', Parameter.POSITIONAL_ONLY, annotation=list_of(params))

            return Signature([args, *session_keywords],
                                           return_annotation=sig.return_annotation)

    def __init__(self, invoker : 'CommandInvoker', /, *, exclude: set[str] = set()):
        '''
        Initializes the command with the given invoker.

        PARAMETERS
        ----------
        invoker: Invoker
            The invoker that is used to invoke the command.
        exclude: set[str]
            The names of the session variables that are excluded from the signature.
        '''
        self.__invoker = invoker
        self.__exclude = exclude
        self.__signature__ = self._signature()

    def __call__(self, args: list[str|Any], **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True
        return self.invoker(*args, **kwargs)

class ArgTransform:
    __name: str
    @property
    def name(self) -> str:
        '''
        The argument name of this applies to.
        '''
        return self.__name

    __declared: type
    @property
    def declared(self) -> type:
        '''
        The annotation which appears on the variable.
        '''
        return self.__declared

    __target: type
    @property
    def target(self) -> type:
        '''
        The type to which the argument is transformed.
        '''
        return self.__target

    __source: type
    @property
    def source(self) -> type:
        '''
        The type from which the argument is transformed.
        '''
        return self.__source

    def __call__(self, arg: Any) -> Any:
        '''
        Transforms the argument into the target type.
        '''
        return arg

    def __init__(self, name: str, /, *,
                 declared: type,
                 target: type,
                 source: type=str) -> None:
        '''
        Initializes the transformation with the given types.
        '''
        self.__name = name
        self.__declared = declared
        self.__target = target
        self.__source = source


class TypeTransform(ArgTransform):
    '''
    A transformation that converts the argument into a different type.
    '''

    def __init__(self, name: str,
                 declared: type,
                 target: type,
                 source: type = str,
                 converter: Callable[[Any], Any] = lambda x: x,
                 completer: Optional[Callable[[Any], Any]] = None,
            ):
        '''
        Initializes the transformation with the given types.

        PARAMETERS
        ----------
        name: str
            The argument name of this applies to.
        declared: type
            The annotation which appears on the variable.
        target: type
            The type to which the argument is transformed.
        source: type
            The type from which the argument is transformed.
        '''
        super().__init__(name,
                         declared=declared,
                         target=target,
                         source=source)
        self.__converter = converter
        self.__completer = completer

    __converter: Callable[[Any], Any]
    @property
    def converter(self) -> Callable[[Any], Any]:
        '''
        The function that is used to convert the argument.
        '''
        return self.__converter

    __completer: Optional[Callable[[Any], Any]]
    @property
    def completer(self) -> Optional[Callable[[Any], Any]]:
        '''
        The function that is used to complete the argument.
        '''
        return self.__completer

    def __call__(self, arg: Any) -> Any:
        '''
        Transforms the argument into the target type.
        '''
        return self.target(arg)

class SessionInvoker(SessionVariablesMixin, SimpleInvoker):
    '''
    An invoker that just does session variable injection.
    '''
    def __init__(self, cmd: Callable,
                 flags: Optional[KeywordInputSpecs] = None,
                 **kwargs):
        '''
        Initializes the invoker with the given command and flags.

        PARAMETERS
        ----------
        cmd: Callable
            The command to be invoked.
        flags: Optional[KeywordInputSpecs]
            The flags that are recognized by the invoker.
        '''
        super().__init__(cmd, flags, **kwargs)

class CommandInvoker(SessionVariablesMixin, Invoker):
    '''
    An invoker that can handle more complex argument parsing that
    involves type checking, name-matching, and conversion.
    '''
    __name: str
    @property
    def name(self) -> str:
        '''
        The name of the command.
        '''
        return self.__name

    __arg_transforms: dict[str, ArgTransform]
    @property
    def arg_transforms(self) -> dict[str, ArgTransform]:
        '''
        The transformations that are applied to the arguments.
        '''
        return self.__arg_transforms

    def __init__(self, cmd: Callable,
                 name: Optional[str] = None,
                 flags: Optional[KeywordInputSpecs] = None,
                 **kwargs):
        super().__init__(cmd, flags, **kwargs)
        self.__arg_transforms = {}
        self.__name = name or cmd.__name__

    __command: 'Command|None' = None
    @property
    def command(self) -> 'Command':
        if self.__command is None:
            self.__command = Command(self)
        return self.__command

    def __call__(self, *args: Any,
                 stderr: IO[str]=sys.stderr,
                 stdout: IO[str]=sys.stdout,
                 stdin: IO[str]=sys.stdin,
                 **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True

        if "--help" in args:
            print(self.__doc__, file=stderr)
            return

        params = self.signature.parameters
        if 'stdout' in params:
            kwargs['stdout'] = stdout
        if 'stderr' in params:
            kwargs['stderr'] = stderr
        if 'stdin' in params:
            kwargs['stdin'] = stdin

        result = super().__call__(*args, **kwargs)

        XSH = self.session_variables['XSH']
        XSH.ctx['_XGIT_RETURN'] = result
        return result

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

    def inject(self, **session_vars):
        '''
        Injects session variables into the invoker.
        '''
        super().inject(**session_vars)

        @contextual_completer
        def completer_subcommands(ctx: CompletionContext):
            return self._complete_subcommands(ctx)
        add_one_completer(self.name, completer_subcommands, 'start')

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
        return {f'{self.prefix} {k}' for k in self.subcommands.keys()}

    def __init__(self,
                 cmd: Callable,
                 prefix: str,
                 flags: Optional[KeywordInputSpecs] = None,
                 **kwargs):
        super().__init__(cmd, prefix, flags, **kwargs)
        self.__prefix = prefix
        self.__subcommands = {}

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
            return subcmd.command(*args[1:], **kwargs)