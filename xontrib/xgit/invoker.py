'''
Utilities for invoking commands based on their signatures.
'''

from collections.abc import Collection, Sequence
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

class Invoker:
    """
    Invokes commands based on their signatures.
    """

    flags: KeywordSpecs
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

    command: Callable
    '''
    The command to be invoked.
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
                    return True, v
                case (0|1|bool()|'+'|'*'), str():
                    return v
                case _:
                    raise ValueError(f"Invalid flag value: {v!r}")
        self.flags = {k:flag_tuple(k, s) for k, s in  flags.items()}

    def invoke(self, args: list[Any], kwargs: dict[str, Any]) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        return self.command(*args, **kwargs)

    def invoke_with_keywords(self, args: list[Any]) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        split = self.extract_keywords(args)
        return self.invoke(*split.args, *split.extra_args,
                           **split.kwargs, **split.extra_kwargs)

    def invoke_with_args(self, args: list[Any], kwargs: dict[str, Any]) -> Any:
        """
        Invokes a command with the given arguments and keyword arguments.

        """
        return self.invoke(args, kwargs)

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
        if not arglist:
            return s
        args: list[Any] = list(arglist)
        def consume_args(arg, n: KeywordSpec, negate: bool = False):
            match *n, negate:
                case bool(b), str(k), False:
                    s.kwargs[k] = b
                case bool(b), str(k), True:
                    s.kwargs[k] = not b
                case 0, str(k), _:
                    s.kwargs[k] = arg
                case 1, str(k), False:
                    s.kwargs[k] = args.pop(0)
                case '+', str(k), False:
                    if len(args) == 0:
                        raise ArgumentError(f"Missing argument for {arg}")
                    l = [args.pop(0)]
                    while args and not (isinstance(args[0], str) and args[0].startswith("-")):
                        l.append(args.pop(0))
                    s.kwargs[k] = l
                case '*', str(k), False:
                    l = []
                    while args and not (isinstance(args[0], str) and args[0].startswith("-")):
                        l.append(args.pop(0))
                    s.kwargs[k] = l
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
                        s.kwargs[k[:2]] = v
                    else:
                        if arg.startswith("--no-") and ((n := self.flags.get(key := arg[5:])) is not None):
                            consume_args(arg, n, True)
                        elif ((n:= self.flags.get(key := arg[2:])) is not None):
                            consume_args(arg, n)
                        elif arg.startswith("--no-"):
                            s.extra_kwargs[arg[5:]] = False
                        else:
                            s.extra_kwargs[arg[2:]] = True
                elif arg.startswith("-"):
                    arg = arg[1:]
                    for c in arg:
                        spec = self.flags.get(c)
                        if spec is not None:
                            consume_args(arg, spec)
                        else:
                            s.extra_kwargs[c] = True
                else:
                    s.args.append(arg)
            else:
                s.args.append(arg)
        return s
