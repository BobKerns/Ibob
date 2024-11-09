'''
Tests of the `xontrib.xgit.proxy` module.
'''

from typing import Any, cast
from types import SimpleNamespace
from functools import wraps

from extracontext import ContextLocal, ContextMap

def test_proxy_loads(module):
    def _t(module, /, **__):
        assert module is not None
    module('xontrib.xgit.proxy', _t)

def test_simple_proxy_map(module):
    def _t(_, proxy, target, **__):
        val = {}
        p = proxy('P', val)
        p['x'] = 42
        assert val['x'] == 42
        assert target(p) is val
        assert p['x'] == 42
    module('xontrib.xgit.proxy', _t)

def test_simple_proxy_object(module):
    def _t(_, proxy, target, **__):
        val = SimpleNamespace()
        p = proxy('P', val)
        p.x = 42
        assert val.x == 42
        assert target(p) is val
        assert p.x == 42
    module('xontrib.xgit.proxy', _t)

def test_module_var(module, debug_env):
    def _t(xgit, /, **__):
        def _t(_, proxy, target, ModuleTargetAccessor, **__):
            assert callable(proxy)
            assert callable(ModuleTargetAccessor)

            p1 = proxy('XGIT', 'xontrib.xgit', ModuleTargetAccessor, key='fish')
            target(p1, 'foo')
            assert 'fish' in xgit.__dict__
            assert xgit.__dict__['fish'] == 'foo'
    module('xontrib.xgit', _t)

def test_identity_var(module, debug_env ):
    def _t(_, *, proxy, target, IdentityTargetAccessor, **__):
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
    module('xontrib.xgit.proxy', _t)


def test_mapping_var(module, debug_env):
    def _t(_, *, proxy, target, MappingTargetAccessor, **__):
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
    module('xontrib.xgit.proxy', _t)


def test_object_var(module, debug_env):
    def _t(_, /, proxy, target, ObjectTargetAccessor, **__):
        val = SimpleNamespace()
        p = proxy('P', val, ObjectTargetAccessor, key='bar')
        t = SimpleNamespace()
        target(p, t)
        assert val.bar is t
        assert target(p) is t
    module('xontrib.xgit.proxy', _t)


def test_context_local_var(module, debug_env):
    def _t(_, proxy, target, ContextLocalAccessor, **__):
        val: Any = ContextLocal()
        p = proxy('P', val, ContextLocalAccessor, key='bar')
        t = SimpleNamespace()
        target(p, t)
        assert val.bar is t
        assert target(p) is t
        p.baz = 'buzz'
        assert t.baz == 'buzz'
        assert p.baz == 'buzz'
    module('xontrib.xgit.proxy', _t)


def test_context_map_var(module, debug_env):
    @wraps(test_context_map_var)
    def _t(_, proxy, target, ContextMapAccessor, **__):
        val: Any = ContextMap()
        p = proxy('P', val, ContextMapAccessor, key='bar')
        t = {}
        target(p, t)
        assert val['bar'] is t
        assert target(p) is t
        p['baz'] = 'buzz'
        assert t['baz'] == 'buzz'
    module('xontrib.xgit.proxy', _t)
