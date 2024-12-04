'''
Unit tests for the global proxy variables.
'''

from collections.abc import MutableMapping

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xonsh.built_ins import XonshSession

def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    XSH: XonshSession = with_xgit.XSH
    assert isinstance(XSH.env, MutableMapping), \
        f"XSH.env not a MutableMapping {XSH.env!r}"

