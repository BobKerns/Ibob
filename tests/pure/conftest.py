'''
Fixtures for pure tests.
'''

import pytest

@pytest.fixture(autouse=True, scope='package')
def lock_out_impure(test_lock):
    '''
    Lock out impure tests from running.
    '''
    with test_lock:
        yield
