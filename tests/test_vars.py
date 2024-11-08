'''
Unit tests for the global proxy variables.
'''

from typing import MutableMapping


def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    xgit, xsh = with_xgit
    assert xsh is not None
    assert isinstance(xsh.env, MutableMapping), \
        f"XSH.env not a MutableMapping {xsh.env!r}"