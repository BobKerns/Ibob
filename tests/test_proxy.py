'''
Tests of the `xontrib.xgit.proxy` module.
'''

from typing import Any, Callable, cast
from types import SimpleNamespace
from functools import wraps

from extracontext import ContextLocal, ContextMap

from xontrib import xgit
from xontrib.xgit.proxy import MappingTargetAccessor, ModuleTargetAccessor, ObjectTargetAccessor

def test_proxy_loads(modules):
    with modules('xontrib.xgit.proxy') as ((m_proxy,), vars):
        assert m_proxy is not None

proxy: Callable[..., Any]
target: Callable[..., Any]
def test_simple_proxy_map(modules):
    with modules('xontrib.xgit.proxy'):
        val = {}
        p = proxy('P', val)
        p['x'] = 42
        assert val['x'] == 42
        assert target(p) is val
        assert p['x'] == 42

def test_simple_proxy_object(modules):
    with modules('xontrib.xgit.proxy'):
        val = SimpleNamespace()
        p = proxy('P', val)
        p.x = 42
        assert val.x == 42
        assert target(p) is val
        assert p.x == 42

xgit: Any
ModuleTargetAccessor: Any
def test_module_var(modules, debug_env):
    with modules('xontrib.xgit.proxy', 'xontrib.xgit') as ((_proxy, _xgit), vars):
        assert callable(proxy)
        assert callable(ModuleTargetAccessor)

        p1 = proxy('XGIT', 'xontrib.xgit', ModuleTargetAccessor, key='fish')
        target(p1, 'foo')
        assert 'fish' in _xgit.__dict__
        assert _xgit.__dict__['fish'] == 'foo'

IdentityTargetAccessor: Any
def test_identity_var(modules, debug_env ):
    with modules('xontrib.xgit.proxy'):
        val = {}
        p = proxy('P', val, IdentityTargetAccessor)
        p['bar'] = 'foo'
        assert val['bar'] == 'foo'
        assert target(p) is val
        val2 = ['dummy']
        target(p, val2)
        p[0] = 'foo'
        assert val2[0] == 'foo'
        assert target(p) is val2

MappingTargetAccessor: Any
def test_mapping_var(modules, debug_env):
    with modules('xontrib.xgit.proxy'):
        val = {}
        p = proxy('P', val, MappingTargetAccessor, key='bar')
        target(p, 'foo')
        assert target(p) == 'foo'
        assert val['bar'] == 'foo'
        val2 = {}
        target(p, val2)
        p['foo'] = 42
        assert val2['foo'] == 42
        assert cast(dict,val['bar'])['foo'] == 42
        assert target(p) is val2

ObjectTargetAccessor: Any
def test_object_var(modules, debug_env):
    with modules('xontrib.xgit.proxy'):
        val = SimpleNamespace()
        p = proxy('P', val, ObjectTargetAccessor, key='bar')
        t = SimpleNamespace()
        target(p, t)
        assert val.bar is t
        assert target(p) is t

ContextLocalAccessor: Any
def test_context_local_var(modules, debug_env):
    with modules('xontrib.xgit.proxy', 'extracontext') as ((_, _proxy), vars):
        val: Any = ContextLocal()
        p = proxy('P', val, ContextLocalAccessor, key='bar')
        t = SimpleNamespace()
        target(p, t)
        assert val.bar is t
        assert target(p) is t
        p.baz = 'buzz'
        assert t.baz == 'buzz'
        assert p.baz == 'buzz'


ContextMapAccessor: Any
def test_context_map_var(modules, debug_env):
    with modules('xontrib.xgit.proxy', 'extracontext') as ((_, _proxy), vars):
        val: Any = ContextMap()
        p = proxy('P', val, ContextMapAccessor, key='bar')
        t = {}
        target(p, t)
        assert val['bar'] is t
        assert target(p) is t
        p['baz'] = 'buzz'
        assert t['baz'] == 'buzz'
