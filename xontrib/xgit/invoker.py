'''
Utilities for invoking commands based on their signatures.
'''

from collections.abc import Collection, Sequence
from functools import cached_property
from math import e
from re import A
from sys import flags
from typing import (
    Any, Callable, NamedTuple, Optional,
)

from inspect import Signature

from xontrib.xgit.type_aliases import (
    KeywordSpec, KeywordSpecs, KeywordInputSpec, KeywordInputSpecs
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

class SimpleInvoker:
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

    command: Callable
    '''
    The command to be invoked.
    '''

    def __init__(self,
                 cmd: Callable,
                 flags: Optional[KeywordInputSpecs] = None,
                 ):
        if not callable(cmd):
            raise ValueError(f"Command must be callable: {cmd!r}")
        self.command = cmd
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

    def invoke_args(self, args: Sequence[Any], kwargs: dict[str, Any] = {}) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        split = self.extract_keywords(args)
        return self.command(*split.args, **{**split.kwargs, **split.extra_kwargs, **kwargs})


    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        try:
            return self.invoke_args(args, kwargs)
        except TypeError as e:
            if e.__traceback__ and e.__traceback__.tb_frame.f_locals.get('self') is self:
                raise ArgumentError(str(e)) from None
            raise

        """
        Invokes a command with the given arguments and keyword arguments.

        """
        split = self.extract_keywords(args)
        return self.__call__(*split.args, *split.extra_args,
                           **split.kwargs, **split.extra_kwargs)

    def invoke_command(self, args: list[Any], kwargs: dict[str, Any], **extra_kwargs) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments

        """
        return self(args, kwargs)

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
                        k, v = arg.split("=", 1)
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
                        spec = flags.get(c)
                        if spec is not None:
                            consume_kw_args(arg, spec)
                        else:
                            s.extra_kwargs[c] = True
                else:
                    s.args.append(arg)
            else:
                s.args.append(arg)
        return s

class Invoker(SimpleInvoker):
    '''
    An invoker that can handle more complex argument parsing that
    involves type checking, name-matching, and conversion.
    '''

    __signature: Signature|None = None
    @property
    def signature(self) -> Signature:
        """
        The signature of the command to be invoked.

        """
        if self.__signature is None:
            self.__signature = Signature.from_callable(self.command)
        return self.__signature

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
                case _, cls if issubclass(cls, bool):
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
