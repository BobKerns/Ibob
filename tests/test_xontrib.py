from importlib import import_module

def test_xgit_loads(module):
    def _t(module, **__):
        assert module is not None
    module('xontrib.xgit', _t)