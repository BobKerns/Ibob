'''
`Runner`s are the generated `Callable` instances` that are used to run
the commands. They are created by the various `Invoker` classes on
being notified that the plugin has been loaded. This supplies them
with the necessary context to run the commands.

The runners are created by the `Invoker` classes, and are not stored in the
the `Invoker` instances. Rather, they are referenced by the `on_unload_xgit`
event handler, which is called when the plugin is unloaded. This event handler
is responsible for disabling the runner and unregistering it from wherever it
is registered.

The `Runner` instances retain a reference to the `Invoker` instance that created
them, to obtain shared data, such as calling signature.
'''

from types import MappingProxyType
from typing import Callable, Generic, Mapping, TypeVar, Any, TYPE_CHECKING
from inspect import Signature, stack

import xonsh

if TYPE_CHECKING:
    from xontrib.xgit.invoker import (
        SessionInvoker, CommandInvoker, PrefixCommandInvoker,
    )

from xontrib.xgit.types import _NO_VALUE, GitNoSessionException, GitValueError, list_of


def _u(s: str) -> str:
    return s.replace('-', '_')

def _h(s: str) -> str:
    return s.replace('_', '-')


C = TypeVar('C', bound='SessionInvoker')

class Runner(Generic[C]):
    '''
    A callable that runs the invoker.
    '''
    __name__: str
    def __init__(self, invoker: 'C', /,
                 **kwargs: Any):
        '''
        Initializes the runner with the given invoker.

        PARAMETERS
        ----------
        invoker: CommandInvoker
            The invoker that is used to invoke the command.
        _exclude: set[str]
            The names of the session variables that are excluded from the signature.
        '''
        self.__invoker = invoker

        self.__doc__ = invoker.__doc__ or self.__doc__ or 'A runner.'
        self.__signature__ = invoker.runner_signature
        self.__annotations__ = invoker.__annotations__
        self.__name__ = invoker.__name__
        self.__qualname__ = invoker.__qualname__
        self.__module__ = invoker.__module__

    def __call__(self, *args, **kwargs):
        return self.invoker(*args, **kwargs)

    def __repr__(self):
        return f'<Runner for {self.invoker.__name__}>'


    __invoker: C
    @property
    def invoker(self) -> C:
        '''
        The invoker that is used to invoke the command.
        '''
        return self.__invoker

    __signature__: Signature
    @property
    def signature(self) -> Signature:
        '''
        The signature of the command.
        '''
        return self.__signature__

    def inject(self, session_args: dict[str, Any]) -> None:
        '''
        Injects the session variables into the command.
        '''
        pass

    def uninject(self) -> None:
        '''
        Removes the session variables from the command.
        '''
        pass


class SessionRunner(Runner['SessionInvoker']):
    '''
    A runner that is used to run a command that requires a session.
    '''
    def __init__(self, invoker: 'SessionInvoker', /, *,
                 _exclude: set[str] = set(),
                 **kwargs: Any):
        '''
        Initializes the runner with the given invoker.

        PARAMETERS
        ----------
        invoker: CommandInvoker
            The invoker that is used to invoke the command.
        _exclude: set[str]
            The names of the session variables that are excluded from the signature.
        '''
        super().__init__(invoker,
                         _exclude=_exclude,
                         **kwargs)

        self.__exclude = _exclude


    @property
    def session_args(self) -> Mapping[str, Any]:
        '''
        The session arguments that are injected into the command.
        '''
        for frame in stack():
            if 'XSH' in frame.frame.f_globals:
                XSH = frame.frame.f_globals['XSH']
            elif 'XSH' in frame.frame.f_locals:
                XSH = frame.frame.f_locals['XSH']
            else:
                continue
            if 'XGIT' in frame.frame.f_globals:
                return {
                    'XSH': xonsh,
                    'XGIT': frame.frame.f_globals['XGIT'],
                }
            if 'XGIT' in XSH.env:
                return {
                    'XSH': XSH,
                    'XGIT': XSH.env['XGIT'],
                }
        raise GitNoSessionException(self.__name__)

    __exclude: set[str] = set()
    @property
    def exclude(self) -> set[str]:
        '''
        The names of the session variables that are excluded from the signature.
        '''
        return self.__exclude

    def __call__(self, *args, **kwargs):
        '''
        Runs the command with the given arguments and keyword arguments.
        '''
        __tracebackhide__ = True
        kwargs.update(self.session_args)
        for key in self.exclude:
            kwargs.pop(key, None)
        return self.invoker(*args, **kwargs)

class Command(SessionRunner):
    '''
    A command that can be invoked with the command-line calling sequence rather than
    the python one. This translates the command-line arguments (strings) into the
    appropriate types and injects session variables into the command.

    A proxy to an `Invoker` that can be called directly with command-line arguments.

    We could use the bound method directly, but that won't allow setting the signature.
    '''

    def __init__(self, invoker : 'CommandInvoker', /, *,
                export: Callable|None = None,
                 **kwargs: Any):
        '''
        Initializes the command with the given invoker.

        PARAMETERS
        ----------
        invoker: Invoker
            The invoker that is used to invoke the command.

        '''
        super().__init__(invoker,
                        **kwargs)
        self.__session_args = None


    __session_args: dict[str, Any]|None
    @property
    def session_args(self) -> Mapping[str, Any]:
        '''
        The session arguments that are injected into the command.
        '''
        if self.__session_args is None:
            raise GitNoSessionException(self.__name__)
        return MappingProxyType(self.__session_args)


    def inject(self, session_args: dict[str, Any]) -> None:
        '''
        Injects the session variables into the command.
        '''
        self.__session_args = session_args

    def uninject(self) -> None:
        '''
        Removes the session variables from the command.
        '''
        self.__session_args = None

    def __call__(self, args: list[str|Any], **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True

        if "--help" in args:
            print(self.__doc__)
            return

        kwargs.update(self.session_args)

        split = self.invoker.extract_keywords(args)
        return self.invoker(*split.args, **split.kwargs, **kwargs)


class PrefixCommand(Command):
    '''
    A command that can be invoked with the command-line calling sequence rather than
    the python one. This translates the command-line arguments (strings) into the
    appropriate types and injects session variables into the command.

    A proxy to an `Invoker` that can be called directly with command-line arguments.

    We could use the bound method directly, but that won't allow setting the signature.
    '''

    __invoker: 'PrefixCommandInvoker'
    @property
    def invoker(self) -> 'PrefixCommandInvoker':
        '''
        The invoker that is used to invoke the command.
        '''
        return self.__invoker

    __subcommands: Mapping[str, 'Command']
    @property
    def subcommands(self) -> MappingProxyType[str, 'Command']:
        '''
        The subcommands that are available to the prefix
        '''
        return MappingProxyType(self.__subcommands)


    def __init__(self, invoker : 'PrefixCommandInvoker', /, *,
                 subcommands: Mapping[str, 'Command'],
                 **kwargs: Any):
        '''
        Initializes the command with the given invoker.

        PARAMETERS
        ----------
        invoker: Invoker
            The invoker that is used to invoke the command.
        subcommands: MappingProxyType[str, CommandInvoker]
            The subcommands that are available to the prefix
        exclude: set[str]
            The names of the session variables that are excluded from the signature.
        '''
        super().__init__(invoker,
                        **kwargs)
        self.__invoker = invoker
        self.__subcommands = subcommands

    def __call__(self, args: list[str|Any], **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True
        subcmd_name = args[0]

        if subcmd_name not in self.subcommands:
            raise GitValueError(f"Invalid subcommand: {subcmd_name}")
        for key in self.__exclude:
            kwargs.pop(key, None)
        subcmd = self.subcommands[subcmd_name]

        return subcmd(args[1:], **kwargs)