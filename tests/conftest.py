import pytest
from importlib import import_module
from typing import Callable, Any
import sys
from contextlib import contextmanager

import xonsh

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
    def loader(mod_name: str, _t: Callable, _as='module'):
        mod = import_module(mod_name)
        return _t(**mod.__dict__, **{_as: mod})

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

@pytest.fixture()
def with_xgit(xonsh_session, module, monkeypatch, ):
    _module = None
    _load: Any = None
    _unload: Any = None
    def _t(module, *, _load_xontrib_, _unload_xontrib_, **__):
        nonlocal _module
        nonlocal _load
        nonlocal _unload
        assert module is not None
        assert callable(_load_xontrib_)
        assert callable(_unload_xontrib_)
        _module = module
        _load = _load_xontrib_
        _unload = _unload_xontrib_

    module('xontrib.xgit', _t)

    _load(xonsh_session)
    yield _module, xonsh_session
    _unload(xonsh_session)
