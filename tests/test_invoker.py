'''
Test the XGit invoker, used for invoking commands based on their signatures.
'''
from pytest import raises

from xontrib.xgit.invoker import Invoker, ArgSplit, ArgumentError

def test_invoker_bad_flags():
    with raises(ValueError) as exc:
        Invoker(lambda:None,
            flags = {'flag1': ['cow']}, # type: ignore
        )

def test_invoker_canonical_flags():
    invoker = Invoker(lambda:None, flags={'a': True, 'b': 0, 'c': 1,
                                          'd': '+', 'e': '*', 'f': False,
                                          'g': 'good'})
    assert invoker.flags == {
        'a': (True, 'a'),
        'b': (0, 'b'),
        'c': (1, 'c'),
        'd': ('+', 'd'),
        'e': ('*', 'e'),
        'f': (False, 'f'),
        'g': (True, 'good'),
    }

def test_invoker_empty():
    invoker = Invoker(lambda:None)
    s = invoker.extract_keywords([])
    assert s.args == []
    assert s.extra_args == []
    assert s.kwargs == {}
    assert s.extra_kwargs == {}


def test_invoker_flag():
    invoker = Invoker(lambda:None, flags = {
        'flag1': True,
        'flag2': (1, 'k_flag2'),
    })
    s = invoker.extract_keywords(['--flag1', '--flag2', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': True, 'k_flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_short_flag():
    invoker = Invoker(lambda:None, flags = {
        'f': (True, 'flag1'),
        'g': (1, 'flag2'),
    })
    s = invoker.extract_keywords(['-f', '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': True, 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_arity_plus():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3, '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3], 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_arity_plus_end():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_arity_plus_short():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    with raises(ArgumentError):
        invoker.extract_keywords(['--flag'])

def test_invoker_arity_star():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3, '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3], 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_arity_star_end():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_arity_star_short():
    invoker = Invoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag'])
    assert s.args == []
    assert s.kwargs == {'flag1': []}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_positional_only():
    invoker = Invoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, 3])
    assert s.args == [1, 2, 3]
    assert s.kwargs == {}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_positional_after():
    invoker = Invoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['-g', 1, 2, 3])
    assert s.args == [2, 3]
    assert s.kwargs == {'flag2': 1}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_positional_before():
    invoker = Invoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, '--flag', 3])
    assert s.args == [1, 2]
    assert s.kwargs == {'flag1': [3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_positional_before_after():
    invoker = Invoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, '-g', 3, 4])
    assert s.args == [1, 2, 4]
    assert s.kwargs == {'flag2': 3}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_invoker_negate_flag():
    invoker = Invoker(lambda:None, flags = {
        })
    s = invoker.extract_keywords(['--no-flag', '--flag2'])
    assert s.args == []
    assert s.kwargs == {}
    assert s.extra_args == []
    assert s.extra_kwargs == {'flag': False, 'flag2': True}

def test_dash_dash_positional():
    invoker = Invoker(lambda:None, flags = {
        })
    s = invoker.extract_keywords(['--flag', 'value', '--', 'value2', '--data'])
    assert s.args == ['value']
    assert s.kwargs == {}
    assert s.extra_args == ['value2', '--data']
    assert s.extra_kwargs == {'flag': True}