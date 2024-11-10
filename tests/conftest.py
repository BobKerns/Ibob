from contextlib import contextmanager
import keyword
from types import ModuleType as Module
from functools import wraps
import pytest
from importlib import import_module
from typing import Callable, Any, NamedTuple, TypeAlias, cast
import sys

from xonsh.built_ins import XonshSession

from xontrib.xgit import context

@pytest.fixture()
def module():
    """
    Call this with the module name, and optionally the name of
    a variable to receive the module. Put the body in a local
    function with the signature (module, **vars) -> None

    def _t(module, *, my_mod_fun, my_mod_var, **_):
        assert callable(my_mod_fun)
        assert my_mod_var == 42
    module('my.module', _t_)

    Where `my_mod_fun` and `my_mod_var` are values of interest in
    the module `my.module`.

    The module, and any modules it load, will be unloaded afterwards.
    """

    modules = set(sys.modules.values())
    @wraps(module)
    def loader(mod_name: str, _t: Callable, _as='module'):
        mod = import_module(mod_name)
        return _t(mod, **mod.__dict__)

    yield loader

    deletions = [k for k, m in sys.modules.items() if m not in modules]
    for k in deletions:
        del sys.modules[k]

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

Loader: TypeAlias = Callable[[XonshSession], dict[str, Any]]

class WithXgit(NamedTuple):
    XSH: XonshSession
    module: Module
    load: Loader|None
    unload: Loader|None

@contextmanager
def session_active(module, xonsh_session):
    if '_load_xontrib_' in module.__dict__:
        _load = module._load_xontrib_
        _load(xonsh_session)
    yield xonsh_session
    if '_unload_xontrib_' in module.__dict__:
        _unload = module._unload_xontrib_
        _unload(xonsh_session)

@pytest.fixture()
def with_xgit(xonsh_session, module, monkeypatch, ):
    def _t(module, *, _load_xontrib_, _unload_xontrib_, XSH=xonsh_session, **kwargs):
        assert module is not None
        assert callable(_load_xontrib_)
        assert callable(_unload_xontrib_)
        load = cast(Loader, _load_xontrib_)
        unload = cast(Loader, _unload_xontrib_)

        def _with_xgit(t: Callable):
             with session_active(module, xonsh_session):
                arg1 = WithXgit(module=module,
                            XSH=xonsh_session,
                            load=load,
                            unload=unload,
                        )
                return t(arg1, **{**arg1._asdict(), **kwargs})
        yield _with_xgit
    yield from module('xontrib.xgit', _t)


