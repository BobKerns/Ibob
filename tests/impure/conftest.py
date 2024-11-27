'''
Fixtures for impure tests.
'''

import pytest

@pytest.fixture(autouse=True, scope='function')
def isolate_tests(test_lock):
    '''
    With each impure test, lock out other tests, both pure and impure.
    '''
    with test_lock:
        yield
