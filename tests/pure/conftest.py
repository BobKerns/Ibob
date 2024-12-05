'''
Fixtures for pure tests.
'''

from contextlib import contextmanager, AbstractContextManager
from typing import (
    Any, Callable, NamedTuple, TypeVar, Optional,
)
from collections.abc import Generator, MutableMapping
import pytest

from xontrib.xgit.types import GitNoSessionException

@pytest.fixture(autouse=True, scope='package')
def lock_out_impure(test_lock):
    '''
    Lock out impure tests from running.
    '''
    with test_lock:
        yield

R = TypeVar('R')

@pytest.fixture()
def f_run(xonsh_session) -> Callable[..., AbstractContextManager[tuple]]:
    '''
    Create a command.
    '''
    from xontrib.xgit.invoker import (
        SharedSessionInvoker, CommandInvoker, _u, _h, KeywordInputSpecs,
    )
    from xontrib.xgit.runners import Runner, Command
    from xontrib.xgit.context import _GitContext
    class CommandSetup(NamedTuple):
        function: Callable[...,Any]
        invoker: SharedSessionInvoker
        command: Runner
        args: tuple
        kwargs: dict
        session_args: dict|None
        result: Any
    @contextmanager
    def f_run_(function: Callable[...,Any], /, *args,
                     expected: tuple,
                     session_args: dict[str,Any]|None = None,
                     invoker_class: type[SharedSessionInvoker] = CommandInvoker,
                     flags: Optional[KeywordInputSpecs] = None,
                     expect_no_session_exception: bool = True,
                     **kwargs) -> Generator[CommandSetup, Any, None]:
        aliases: dict[str, Callable[...,Any]] = {}
        exports: dict[str, Any] = {}
        def _export(func: Any, name: str|None):
            name = _h(func.__name__) if name is None else _h(name)
            exports[name] = func
        invoker = invoker_class(function, function.__name__,
                                flags=flags,
                                export=_export,
                                )
        XSH = xonsh_session
        aliases = XSH.aliases
        assert isinstance(aliases, MutableMapping)
        from xonsh.events import events
        if session_args is None:
            session_args = {
                'XSH': XSH,
                'XGIT': _GitContext(XSH),
            }
        runner = invoker.create_runner(
            _export=_export,
            _EXTRA='foo',)
        invoker._perform_injections(runner, **session_args) 
        invoker._register_runner(runner, **session_args)
        if expect_no_session_exception:
            with pytest.raises(GitNoSessionException):
                runner(*args, **kwargs)
                yield CommandSetup(
                           function=function,
                           invoker=invoker,
                           command=runner,
                           args=args,
                           kwargs=kwargs,
                           session_args=session_args,
                           result=None,
                        )
                return
        #events.on_xgit_loaded.fire(XSH=XSH)
        result = runner(*args, **kwargs)
        # Commands must wrap their returns to suppress xonsh output.
        if isinstance(runner, Command):
            assert isinstance(result, tuple)
            assert len(result) == 4
            assert result[0] is None
            assert result[1] is None
            assert result[2] == 0
            result = result[3]
            if runner.for_value:
                assert result == XSH.ctx['$']
                del XSH.ctx['$']
        yield CommandSetup(
                           function=function,
                           invoker=invoker,
                           command=runner,
                           args=args,
                           kwargs=kwargs,
                           session_args=session_args,
                           result=result,
                           )
        assert result == expected
        assert '_EXTRA' not in runner.session_args
        if issubclass(invoker_class, CommandInvoker):
            name = runner.invoker.name
            assert name in aliases
            if _export is not None:
                assert _u(function.__name__) in exports
            events.on_xgit_unload.fire(XSH=XSH)
            assert name not in aliases, 'Cleanup failed: alias not removed'
    return f_run_