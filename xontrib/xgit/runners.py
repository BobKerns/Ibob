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
from collections.abc import Mapping
from typing import (
    Callable, Generic, TypeVar, Any, TYPE_CHECKING,
)
from inspect import Signature, stack

import xonsh
from xonsh.built_ins import XonshSession

if TYPE_CHECKING:
    from xontrib.xgit.invoker import (
        Invoker, SharedSessionInvoker,
        CommandInvoker, PrefixCommandInvoker,
        BaseSessionInvoker, RunnerPerSessionInvoker,
    )

from xontrib.xgit.types import (
    GitNoSessionException, GitValueError, ValueHandler,
)


def _u(s: str) -> str:
    return s.replace('-', '_')

def _h(s: str) -> str:
    return s.replace('_', '-')


C = TypeVar('C', bound='Invoker')

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
        invoker: BaseInvoker
            The invoker that is used to invoke the command.
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

    def inject(self, /,
               **session_args: Any) -> None:
        '''
        Injects the session variables into the command.
        '''
        pass

    def uninject(self) -> None:
        '''
        Removes the session variables from the command.
        '''
        pass


BSI = TypeVar('BSI', bound='BaseSessionInvoker')
class BaseSessionRunner(Generic[BSI], Runner['BSI']):
    '''
    A runner that is used to run a command that requires a session.
    '''
    def __init__(self, invoker: BSI, /,
                 **kwargs: Any):
        '''
        Initializes the runner with the given invoker.

        PARAMETERS
        ----------
        invoker: BaseSessionInvoker
            The invoker that is used to invoke the command.
        '''
        super().__init__(invoker, **kwargs)

    @property
    def session_args(self) -> Mapping[str, Any]:
        '''
        The session arguments that are injected into the command.
        '''
        ...

    def __call__(self, *args, **kwargs):
        '''
        Runs the command with the given arguments and keyword arguments.
        '''
        __tracebackhide__ = True
        kwargs.update(self.session_args)
        return self.invoker(*args, **kwargs)


SSI = TypeVar('SSI', bound='SharedSessionInvoker')
class SharedSessionRunner(Generic[SSI], BaseSessionRunner['SSI']):
    '''
    A runner that is used to run a command that requires a session.
    '''
    def __init__(self, invoker: SSI, /, **kwargs: Any):
        '''
        Initializes the runner with the given invoker.

        PARAMETERS
        ----------
        invoker: SharedSessionInvoker
            The invoker that is used to invoke the command.
        '''
        super().__init__(invoker, **kwargs)

    @property
    def session_args(self) -> Mapping[str, Any]:
        '''
        Find the session arguments to inject into the command.
        '''
        for frame in stack():
            if 'XSH' in frame.frame.f_globals:
                XSH = frame.frame.f_globals['XSH']
            elif 'XSH' in frame.frame.f_locals:
                XSH = frame.frame.f_locals['XSH']
            else:
                continue
            if not isinstance(XSH, XonshSession):
                continue
            if 'XGIT' in frame.frame.f_globals:
                return {
                    'XSH': xonsh,
                    'XGIT': frame.frame.f_globals['XGIT'],
                }
            if XSH.env is not None and 'XGIT' in XSH.env:
                return {
                    'XSH': XSH,
                    'XGIT': XSH.env['XGIT'],
                }
        raise GitNoSessionException(self.__name__)

    def __call__(self, *args, **kwargs):
        '''
        Runs the command with the given arguments and keyword arguments.
        '''
        __tracebackhide__ = True
        kwargs.update(self.session_args)
        return self.invoker(*args, **kwargs)


RPSI = TypeVar('RPSI', bound='RunnerPerSessionInvoker')

class RunnerPerSessionRunner(BaseSessionRunner[RPSI]):
    '''
    A `Runner` that is used to run a function that requires a session, and which
    can be registered per session. It is created and registered when the `Invoker`
    is notified that the plugin has been loaded (which is when the session is
    available).
    '''

    def __init__(self, invoker: RPSI, /, **kwargs: Any):
        '''
        Initializes the runner with the given invoker.

        PARAMETERS
        ----------
        invoker: RunnerPerSessionInvoker
            The invoker that is used to invoke the command.
        '''
        super().__init__(invoker, **kwargs)
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

    def inject(self, /,
               **session_args: Any) -> None:
        '''
        Injects the session variables into the command.
        '''
        sig = self.signature
        self.__session_args = {k:v for k,v in session_args.items()
                                 if k in sig.parameters}

    def uninject(self) -> None:
        '''
        Removes the session variables from the command.
        '''
        self.__session_args = None

    def __call__(self, *args, **kwargs):
        '''
        Runs the command with the given arguments and session arguments.
        '''
        __tracebackhide__ = True
        kwargs.update(self.session_args)
        return self.invoker(*args, **kwargs)


class EventRunner(RunnerPerSessionRunner['EventInvoker']):
    '''
    A runner that is used to run an event that requires a session.
    '''

    def uninject(self) -> None:
        '''
        Removes the session variables from the command.
        '''
        self.invoker.event.discard(self)


class Command(RunnerPerSessionRunner['CommandInvoker']):
    '''
    A command that can be invoked with the command-line calling sequence rather than
    the python one. This translates the command-line arguments (strings) into the
    appropriate types and injects session variables into the command.

    A proxy to an `Invoker` that can be called directly with command-line arguments.

    We could use the bound method directly, but that won't allow setting the signature.
    '''

    __for_value: bool
    @property
    def for_value(self) -> bool:
        '''
        Whether the command is for a value.
        '''
        return self.__for_value
    

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
        self.__for_value = invoker.for_value


    __value_handler: ValueHandler
    def inject(self, /, *,
               value_handler: ValueHandler=lambda x:x,
               **session_args: Any) -> None:
        '''
        Injects the session variables into the command.
        '''
        super().inject(**session_args)
        self.__value_handler = value_handler


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
        return self.__value_handler(self.invoker(*split.args,
                                                 **split.kwargs,
                                                 **kwargs))


class PrefixCommand(Command):
    '''
    A command that can be invoked with the command-line calling sequence rather than
    the python one. This translates the command-line arguments (strings) into the
    appropriate types and injects session variables into the command.

    A proxy to an `Invoker` that can be called directly with command-line arguments.

    We could use the bound method directly, but that won't allow setting the signature.
    '''

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
        invoker: PrefixCommandInvoker
            The invoker that is used to invoke the command.
        subcommands: MappingProxyType[str, CommandInvoker]
            The subcommands that are available to the prefix
        '''
        super().__init__(invoker,
                        **kwargs)
        self.__subcommands = subcommands


    def __call__(self, args: list[str|Any], **kwargs: Any) -> Any:
        '''
        Invokes the command with the given arguments and keyword arguments.

        '''
        __tracebackhide__ = True
        subcmd_name = args.pop(0)

        if subcmd_name not in self.subcommands:
            raise GitValueError(f"Invalid subcommand: {subcmd_name}")
        subcmd = self.subcommands[subcmd_name]

        return subcmd(args, **kwargs)