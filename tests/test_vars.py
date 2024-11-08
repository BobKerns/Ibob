'''
Unit tests for the global proxy variables.
'''

from typing import Mapping


def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    xgit, xsh = with_xgit
    assert xsh is not None
    assert isinstance(xsh.env, Mapping)