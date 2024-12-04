'''
Test that the xgit module loads successfully.
'''

def test_xgit_loads(modules):
    with modules('xontrib.xgit') as ((m_xgit,), vars):
        assert m_xgit is not None