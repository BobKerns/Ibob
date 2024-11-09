'''
Unit tests for the global proxy variables.
'''

from typing import MutableMapping


def test_xsh(with_xgit):
    '''
    Test the xsh proxy.
    '''
    def _t(*_, XSH, **__):
        assert isinstance(XSH.env, MutableMapping), \
            f"XSH.env not a MutableMapping {XSH.env!r}"
    with_xgit(_t)