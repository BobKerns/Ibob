'''
Unit tests for the global proxy variables.
'''

from typing import Any, MutableMapping

from xonsh.built_ins import XonshSession

from xontrib.xgit.proxy_json import proxy_to_json

def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    def _t(*_, XSH: XonshSession, **__):
        print(f"XSH: {proxy_to_json(XSH)!r}")
        assert isinstance(XSH.env, MutableMapping), \
            f"XSH.env not a MutableMapping {XSH.env!r}"
    with_xgit(_t)