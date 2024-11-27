'''
Unit tests for the global proxy variables.
'''

from typing import Any, MutableMapping

from xonsh.built_ins import XonshSession

def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    XSH = with_xgit.XSH
    assert isinstance(XSH.env, MutableMapping), \
        f"XSH.env not a MutableMapping {XSH.env!r}"

