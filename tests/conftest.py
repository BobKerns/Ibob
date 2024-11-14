from contextlib import contextmanager
from inspect import currentframe, stack
from threading import RLock
from types import ModuleType as Module
import pytest
from importlib import import_module
from typing import Callable, Any, Generator, NamedTuple, TypeAlias, cast
import sys

from xonsh.built_ins import XonshSession


def cleanup(target: dict[str, Any], before: dict[str, Any], loaded: dict[str, Any], after: dict[str, Any]):
    '''
    Undo additions and deletionis, while preserving modifications.
    '''
    all_vars = after.keys() | loaded.keys() | before.keys()
    for k in all_vars:
        if k in after and k not in loaded:
            # This is a variable that was added by the test
            pass
        elif k in after and k in loaded and (after[k] is not loaded[k]):
            # This is a variable that was modified by the test
            pass
        elif k not in after and k in loaded:
            # This is a variable that was deleted by the test
            pass
        elif k not in before and k in loaded:
            # This is a variable that was added by the fixture
            del target[k]
        elif k in before and k not in loaded:
            # This is a variable that was deleted by the fixture
            target[k] = before[k]
        elif k in before and k in loaded and (before[k] is not loaded[k]):
            # This is a variable that was modified by the fixture
            target[k] = before[k]
        else:
            # This is a variable that was not touched by either
            pass

@pytest.fixture()
def sysdisplayhook(with_events):
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
def modules():
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
        existing_outer_modules = dict(sys.modules)
        @contextmanager
        def modules(*mod_names: str):
            with modules_lock:
                top = currentframe() or stack()[0].frame
                frame = top.f_back
                assert frame is not None
                frame = frame.f_back
                assert frame is not None
                f_globals = frame.f_globals
                before_inner_modules = dict(sys.modules)
                before = dict(f_globals)
                mods = [import_module(m) for m in mod_names]
                loaded_inner_modules = dict(sys.modules)
                kwargs = {
                    k:v
                    for m in reversed(mods)
                    for k,v in m.__dict__.items()
                }
                f_globals.update(kwargs)
                loaded = dict(f_globals)
                try:
                    yield LoadedModules(modules=mods, variables=kwargs)
                finally:
                    after = dict(f_globals)
                    after_inner_modules = dict(sys.modules)
                    cleanup(f_globals, before, loaded, after)
                    cleanup(sys.modules, before_inner_modules, loaded_inner_modules, after_inner_modules)

        try:
            yield modules
        finally:
            sys.modules.clear()
            sys.modules.update(existing_outer_modules)

@pytest.fixture(autouse=True)
def debug_env(monkeypatch  ):
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
    
@pytest.fixture(autouse=True)
def clean_modules():
    """
    Ensure a clean module namespace before and after each test.
    """
    import sys
    for k in list(sys.modules.keys()):
        if k.startswith('xontrib.xgit'):
            del sys.modules[k]
    try:
        yield
    finally:
        for k in list(sys.modules.keys()):
            if k.startswith('xontrib.xgit'):
                del sys.modules[k]

Loader: TypeAlias = Callable[[XonshSession], dict[str, Any]]

class XontribModule(NamedTuple):
    XSH: XonshSession
    module: Module
    load: Loader|None
    unload: Loader|None

@contextmanager
def session_active(module, xonsh_session) -> Generator[XontribModule, None, None]:
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
def with_xgit(xonsh_session, modules, sysdisplayhook):
    with modules('xontrib.xgit') as ((module,), kwargs):
        assert module is not None
        _load_xontrib_ = module.__dict__['_load_xontrib_']
        _unload_xontrib_ = module.__dict__['_unload_xontrib_']
        assert callable(kwargs['_load_xontrib_'])
        assert callable(kwargs['_unload_xontrib_'])
        load = cast(Loader, _load_xontrib_)
        unload = cast(Loader, _unload_xontrib_)

        def _with_xgit(t: Callable):
             with session_active(module, xonsh_session) as xontrib_module:
                return t(xontrib_module, **{**xontrib_module._asdict(), **kwargs})
        yield _with_xgit

CWD_LOCK = RLock()
@pytest.fixture()
def chdir():
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
def with_events():
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
        if k.startswith('on_') and hasattr(getattr(events, k), '_handlers'):
            if k not in existing:
                delattr(events, k)    