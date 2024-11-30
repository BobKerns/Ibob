'''
Fixtures for pure tests.
'''

from contextlib import contextmanager
from typing import (
    Any, Callable, Generator, NamedTuple, TypeVar, Generic,
    ContextManager, Optional, Sequence,
)
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
def run_command() -> Callable[..., ContextManager[tuple]]:
    '''
    Create a command.
    '''
    from xontrib.xgit.invoker import (
        SessionInvoker, CommandInvoker, _u, _h, KeywordInputSpecs,
    )
    from xontrib.xgit.runners import Runner
    from xontrib.xgit.context import _GitContext
    class CommandSetup(NamedTuple, Generic[R]):
        function: Callable[...,R]
        invoker: SessionInvoker
        command: Runner
        args: tuple
        kwargs: dict
        session_args: dict|None
        result: Any
    @contextmanager
    def run_command_(function: Callable[...,R], /, *args,
                     expected: tuple,
                     session_args: dict[str,Any]|None = None,
                     invoker_class: type[SessionInvoker] = CommandInvoker,
                     flags: Optional[KeywordInputSpecs] = None,
                     expect_no_session_exception: bool = True,
                     **kwargs) -> Generator[CommandSetup[R], Any, None]:
        aliases: dict[str, Callable[...,Any]] = {}
        exports: dict[str, Any] = {}
        def _export(func: Any, name: str|None):
            if name is None:
                name = _h(func.__name__)
            else:
                name = _h(name)
            exports[name] = func
        invoker = invoker_class(function, flags=flags)
        if session_args is None:
            from xonsh.built_ins import XSH
            session_args = {
                'XSH': XSH,
                'XGIT': _GitContext(XSH),
            }
        runner = invoker.create_runner(
            _aliases=aliases,
            _export=_export,
            _EXTRA='foo',)
        runner.inject(session_args)
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
        result = runner(*args, **kwargs)
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
            assert _h(function.__name__) in aliases
            if _export is not None:
                assert _u(function.__name__) in exports
        runner.uninject()
        assert aliases == {}, 'Cleanup failed: aliases not empty'
    return run_command_