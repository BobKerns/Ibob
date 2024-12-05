'''
Test that the xgit module loads successfully.
'''

def test_xgit_loads():
    from xontrib.xgit import _load_xontrib_, _unload_xontrib_
    assert callable(_load_xontrib_)
    assert callable(_unload_xontrib_)