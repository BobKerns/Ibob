
from contextlib import contextmanager
from threading import RLock, Lock
from types import ModuleType as Module
import pytest
from importlib import import_module
from typing import (
    Callable, Any, NamedTuple, TypeAlias
)
from collections.abc import Generator
import sys
from xonsh.built_ins import XonshSession


def run_stdout(args, **kwargs):
    from subprocess import run, PIPE
    return run(args, check=True, stdout=PIPE, text=True, **kwargs).stdout


@pytest.fixture()
def sysdisplayhook(f_events):
    """
    Fixture to capture the current sys.displayhook and restore it afterwards.
    """
    with modules_lock:
        old_displayhook = sys.displayhook
        try:
            yield
        finally:
            sys.displayhook = old_displayhook

class LoadedModules(NamedTuple):
    modules: list[Module]
    variables: dict[str, Any]

modules_lock = RLock()
@pytest.fixture()
def f_modules():
    """
    Fixture to load a module or modules for testing.

    This is a context manager that takes the names
    of modules to load into the local namespace, and
    then unloads them afterwards.

    Usage:

    def test_my_module(modules):
        with modules('my.module'):
            assert callable(my_function_from_my_module)

    The module, and any modules it load, will be unloaded afterwards.
    """
    with modules_lock:
        @contextmanager
        def modules(*mod_names: str):
            with modules_lock:
                mods = [import_module(m) for m in mod_names]
                kwargs = {
                    k:v
                    for m in reversed(mods)
                    for k,v in m.__dict__.items()
                }
                try:
                    yield LoadedModules(modules=mods, variables=kwargs)
                finally:
                    pass

        try:
            yield modules
        finally:
            pass

@pytest.fixture(autouse=True)
def f_debug_env(monkeypatch  ):
    monkeypatch.setenv("XGIT_TRACE_LOAD", "1")
    monkeypatch.setenv("XGIT_TRACE_DISPLAY", "1")
    monkeypatch.setenv("XGIT_TRACE_COMMANDS", "1")
    monkeypatch.setenv("XGIT_TRACE_OBJECTS", "1")
    monkeypatch.setenv("XGIT_TRACE_REFERENCES", "1")
    monkeypatch.setenv("XGIT_TRACE_CONTEXTS", "1")
    monkeypatch.setenv("XGIT_TRACE_VARS", "1")
    monkeypatch.setenv("XGIT_TRACE_PROXY", "1")
    monkeypatch.setenv("XGIT_TRACE_TARGET", "1")
    monkeypatch.setenv("XONSH_SHOW_TRACEBACK", "1")
    monkeypatch.setenv("XONSH_TRACE_SUBPROC", "1")


Loader: TypeAlias = Callable[[XonshSession], dict[str, Any]]

class XontribModule(NamedTuple):
    XSH: XonshSession
    module: Module
    load: Loader|None
    unload: Loader|None

@contextmanager
def session_active(module, xonsh_session,
                   ) -> Generator[XontribModule, None, None]:
    '''
    Context manager to load and unload a xontrib module.
    '''
    _load = None
    _unload = None
    if '_load_xontrib_' in module.__dict__:
        _load = module._load_xontrib_

    if '_unload_xontrib_' in module.__dict__:
        _unload = module._unload_xontrib_
    if _load is not None:
        _load(xonsh_session)
    yield XontribModule(
        XSH=xonsh_session,
        module=module,
        load=_load,
        unload=_unload)
    if _unload is not None:
        _unload(xonsh_session)

@pytest.fixture()
def with_xgit(xonsh_session, f_modules, sysdisplayhook):
    import xontrib.xgit as xgit
    with session_active(xgit, xonsh_session) as xontrib_module:
            yield xontrib_module


CWD_LOCK = RLock()
@pytest.fixture()
def f_chdir():
    '''
    Change the working directory for the duration of the test.
    Locks to prevent simultaneous changes.
    '''
    from pathlib import Path
    import os
    def chdir(path) -> Path:
        path = Path(path)
        os.chdir(path)
        return path

    with CWD_LOCK:
        old = Path.cwd()
        try:
            yield chdir
        finally:
            os.chdir(old)

@pytest.fixture()
def f_events():
    from xonsh.events import events
    existing = {
        k: set(getattr(events, k))
        for k in dir(events)
        if k.startswith('on_')
        if hasattr(getattr(events, k), '_handlers')}
    yield events
    for k, v in existing.items():
        getattr(events, k)._handlers.clear()
        getattr(events, k)._handlers.update(v)
    for k in dir(events):
        if (
            k.startswith('on_') and hasattr(getattr(events, k), '_handlers')
            and k not in existing
        ):
            delattr(events, k)


_test_lock: Lock = Lock()
@pytest.fixture(scope='session')
def test_lock():
    '''
    Fixture to lock tests that cannot be run in parallel.
    '''
    yield _test_lock
