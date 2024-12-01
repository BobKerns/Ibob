'''
Test the XGit invoker, used for invoking commands based on their signatures.
'''
from typing import IO
from pytest import raises

from inspect import Signature, signature

from xonsh.built_ins import XonshSession

from xontrib.xgit.invoker import (
    SessionInvoker, SimpleInvoker, Invoker, ArgSplit, ArgumentError,
    CommandInvoker,
)
from xontrib.xgit.types import GitNoSessionException

def test_simple_invoker_bad_flags():
    with raises(ValueError) as exc:
        SimpleInvoker(lambda:None,
            flags = {'flag1': ['cow']}, # type: ignore
        )

def test_simple_invoker_canonical_flags():
    invoker = SimpleInvoker(lambda:None, flags={'a': True, 'b': 0, 'c': 1,
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

def test_simple_invoker_empty():
    invoker = SimpleInvoker(lambda:None)
    s = invoker.extract_keywords([])
    assert s.args == []
    assert s.extra_args == []
    assert s.kwargs == {}
    assert s.extra_kwargs == {}


def test_simple_invoker_flag():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag1': True,
        'flag2': (1, 'k_flag2'),
    })
    s = invoker.extract_keywords(['--flag1', '--flag2', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': True, 'k_flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_short_flag():
    invoker = SimpleInvoker(lambda:None, flags = {
        'f': (True, 'flag1'),
        'g': (1, 'flag2'),
    })
    s = invoker.extract_keywords(['-f', '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': True, 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_arity_plus():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3, '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3], 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_arity_plus_end():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_arity_plus_short():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('+', 'flag1'),
        'g': (1, 'flag2'),
        })
    with raises(ArgumentError):
        invoker.extract_keywords(['--flag'])

def test_simple_invoker_arity_star():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3, '-g', 'value'])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3], 'flag2': 'value'}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_arity_star_end():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag', 1, 2, 3])
    assert s.args == []
    assert s.kwargs == {'flag1': [1, 2, 3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_arity_star_short():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['--flag'])
    assert s.args == []
    assert s.kwargs == {'flag1': []}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_positional_only():
    invoker = SimpleInvoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, 3])
    assert s.args == [1, 2, 3]
    assert s.kwargs == {}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_positional_after():
    invoker = SimpleInvoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords(['-g', 1, 2, 3])
    assert s.args == [2, 3]
    assert s.kwargs == {'flag2': 1}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_positional_before():
    invoker = SimpleInvoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, '--flag', 3])
    assert s.args == [1, 2]
    assert s.kwargs == {'flag1': [3]}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_positional_before_after():
    invoker = SimpleInvoker(lambda x: x, flags = {
        'flag': ('*', 'flag1'),
        'g': (1, 'flag2'),
        })
    s = invoker.extract_keywords([1, 2, '-g', 3, 4])
    assert s.args == [1, 2, 4]
    assert s.kwargs == {'flag2': 3}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_simple_invoker_negate_flag_undeclared():
    invoker = SimpleInvoker(lambda:None, flags = {
        })
    s = invoker.extract_keywords(['--no-flag', '--flag2'])
    assert s.args == []
    assert s.kwargs == {}
    assert s.extra_args == []
    assert s.extra_kwargs == {'flag': False, 'flag2': True}

def test_simple_invoker_negate_flag_undeclared_hyphen():
    invoker = SimpleInvoker(lambda:None, flags = {
        })
    s = invoker.extract_keywords(['--no-flag-1', '--flag-2'])
    assert s.args == []
    assert s.kwargs == {}
    assert s.extra_args == []
    assert s.extra_kwargs == {'flag_1': False, 'flag_2': True}

def test_simple_invoker_negate_flag_declared():
    invoker = SimpleInvoker(lambda:None, flags = {
        'flag': True, 'flag2': False,
        })
    s = invoker.extract_keywords(['--no-flag', '--no-flag2'])
    assert s.args == []
    assert s.kwargs == {'flag': False, 'flag2': True}
    assert s.extra_args == []
    assert s.extra_kwargs == {}

def test_dash_dash_positional():
    invoker = SimpleInvoker(lambda:None,
                      flags = {
        })
    s = invoker.extract_keywords(['--flag', 'value', '--', 'value2', '--data'])
    assert s.args == ['value']
    assert s.kwargs == {}
    assert s.extra_args == ['value2', '--data']
    assert s.extra_kwargs == {'flag': True}

def test_simple_invoker_invoke():
    def f(a, b, c):
        return a, b, c
    invoker = SimpleInvoker(f)
    assert invoker.__call__(1, 2, 3) == (1, 2, 3)

def test_simple_invoker_invoke_kw():
    def f(a, b, c):
        return a, b, c
    invoker = SimpleInvoker(f)
    assert invoker.__call__(a=1, b=2, c=3) == (1, 2, 3)

def test_simple_invoker_invoke_short():
    def f(a, b, c):
        return a, b, c
    invoker = SimpleInvoker(f)
    with raises(ArgumentError):
        invoker.__call__(1, 2)

def test_simple_invoker_invoke_extra():
    def f(a, b, c):
        return a, b, c
    invoker = SimpleInvoker(f)
    with raises(ArgumentError):
        invoker.__call__(1, 2, 3, 4)

def test_simple_invoker_invoke_extra_kw():
    # SimpleInvoker doesn't support extra kwargs
    def f(a, b, c):
        return a, b, c
    invoker = SimpleInvoker(f)
    with raises(ArgumentError):
        invoker.__call__(a=1, b=2, c=3, d=4)

def test_simple_invoker_invoke_extra_kw_extra():
    def f(a, b, c, **kwargs):
        return a, b, c, kwargs
    invoker = SimpleInvoker(f)
    assert invoker.__call__(a=1, b=2, c=3, d=4) == (1, 2, 3, {'d': 4})

def test_invoker_signature():
    def f(a, b, c):
        return a, b, c
    invoker = Invoker(f)
    sig = invoker.signature
    assert isinstance(sig, Signature)
    assert len(sig.parameters) == 3

def test_invoker_flags():
    def f(a, b:bool, c):
        return a, b, c
    invoker = Invoker(f)
    assert invoker.flags == {
        'a': (1, 'a'),
        'b': (True, 'b'),
        'c': (1, 'c'),
    }

def test_invoker_positional_only_flags():
    def f(a, b:bool, c, /):
        return a, b, c
    invoker = Invoker(f)
    assert invoker.flags == {
        'b': (True, 'b'),
    }

def test_invoker_positional_only_flags_extra():
    def f(a, b:bool, c, /, **kwargs):
        return a, b, c, kwargs
    invoker = Invoker(f)
    assert invoker.flags == {
        'b': (True, 'b'),
    }

def test_invoker_positional_only_flags_extra_kw():
    def f(a, b:bool, c, /, **kwargs):
        return a, b, c, kwargs
    invoker = Invoker(f)
    assert invoker(1, True, 3, d=4) == (1, True, 3, {'d': 4})

def test_invoker_extra_positional():
    def f(a, b:bool, c, /, **kwargs):
        return a, b, c, kwargs
    #with raises(ArgumentError):
    invoker = Invoker(f)
    with raises(ArgumentError):
        invoker(1, True, 3, 4)

def test_invoker_extra_positional_accept():
    def f(a, b:bool, c, /, *args, **kwargs):
        return a, b, c, args, kwargs
    invoker = Invoker(f)
    assert invoker(1, True, 3, 4, d=5) == (1, True, 3, (4,), {'d': 5})

def test_invoker_extra_positional_accept_no_kwargs():
    def f(a, b:bool, c, /, *args, e='no e'):
        return a, b, c, e, args
    invoker = Invoker(f)
    assert invoker(1, True, 3, 4) == (1, True, 3, 'no e', (4,))
    assert invoker(1, True, 3) == (1, True, 3, 'no e', ())
    with raises(ArgumentError):
        invoker(1, True, 3, d=4)
    with raises(ArgumentError):
        invoker(1, True, 3, 4, d=5)
    with raises(ArgumentError):
        invoker(1, True, 3, c=4)
    with raises(ArgumentError):
        invoker(1, True, c=4)
    assert invoker(1, True, 3, e=4) == (1, True, 3, 4, ())

def test_invoker_cmdline_keyword_1():
    def f(a, b:bool, c, /, *args, e='no e'):
        return a, b, c, e, args
    invoker = Invoker(f)
    s = invoker.extract_keywords([1, True, 3, 4, '--e', 5])
    assert s.args == [1, True, 3, 4]
    assert s.kwargs == {'e': 5}
    assert s.extra_kwargs == {}
    assert invoker(1, True, 3, 4, '--e', 5) == (1, True, 3, 5, (4,))

def test_command_empty(run_command):
    def f() -> int:
        return 1
    with run_command(f, [],
                     expected=1,
                     expect_no_session_exception=False,
                     ) as cmd_info:
        pass


def test_command_positional(run_command):
    def f(a:int, b:bool, c:str) -> int:
        return 1
    with run_command(f, [1, True, '3'],
                     expected=1,
                     expect_no_session_exception=False,
                     ) as cmd_info:
        assert cmd_info.invoker.signature.parameters['a'].annotation == int
        assert cmd_info.invoker.signature.parameters['b'].annotation == bool
        assert cmd_info.invoker.signature.parameters['c'].annotation == str
        assert cmd_info.invoker.signature.return_annotation == int
        #assert next(iter(cmd_info.command.signature.parameters.values())).annotation == list
        # It's more complex than just list.

def test_command_positional_extra(run_command):
    def f(a:int, b:bool, c:str, /, *args) -> int:
        return 1
    with run_command(f, [1, True, '3', 4],
                     expected=1,
                     expect_no_session_exception=False,
                     ) as cmd_info:
        assert cmd_info.invoker.signature.parameters['a'].annotation == int
        assert cmd_info.invoker.signature.parameters['b'].annotation == bool
        assert cmd_info.invoker.signature.parameters['c'].annotation == str
        assert cmd_info.invoker.signature.return_annotation == int

def test_command_positional_extra_kw(run_command):
    def f(a:int, b:bool, c:str, /, *args, **kwargs):
        return  a, b, c, args, kwargs.keys()
    with run_command(f,[1,True, '3', 4, '--d', 5],
                     expect_no_session_exception=False,
                     flags={'d': 1},
                     expected=(1, True, '3', (4,), {'d'})) as cmd_info:
        pass

def test_command_positional_decl_extra_kw(run_command):
    def f(a:int, b:bool, c:str, /, *args, d: bool, **kwargs):
        return  a, b, c, args, d, kwargs.keys()
    with run_command(f, [1, True, '3', 4, '--d', 5],
                     flags={'d': True},
                     expected=(1, True, '3', (4,5), True, set()),
                     expect_no_session_exception=False,) as cmd_info:
        pass

def test_command_kw_equals(run_command ):
    def f(a:int, b:bool, c:str, /, *args, d: str, **kwargs):
        return  a, b, c, args, d, kwargs.keys()
    with run_command(f, [1, True, '3', 4, '--d=30'],
                expected=(1, True, '3', (4,), '30', set()),
                expect_no_session_exception=False,
                ) as cmd_info:
        pass

def test_session_invoker():
    def f(a:int, b:bool, c:str, /, *args, session: str, **kwargs):
        return  a, b, c, args, session, kwargs
    invoker = SessionInvoker(f)
    assert invoker(1, True, '3', 4, session='session-1') == (1, True, '3', (4,), 'session-1', {})

def test_session_invoker_more_kw():
    def f(a:int, b:bool, c:str, /, *args, **kwargs):
        return  a, b, c, args, kwargs
    invoker = SessionInvoker(f)
    result = invoker(1, True, '3', 4,
                            extra='fun')
    assert result == (
        1, True, '3', (4,), {
            'extra': 'fun'
        })

def test_session_invoker_no_session():
    def f(a:int, b:bool, c:str, /, *args, XSH=None, **kwargs):
        return  a, b, c, args, XSH, kwargs
    invoker = SessionInvoker(f)
    runner = invoker.create_runner()
    with raises(GitNoSessionException):
        runner(1, True, '3', 4)


def test_session_invoker_clear_session(xonsh_session):
    from xontrib.xgit.runners import Command
    def f(a:int, b:bool, c:str, /, *args, XSH: XonshSession, **kwargs):
        return  a, b, c, args, XSH, kwargs
    invoker = CommandInvoker(f, aliases={})
    _aliases = {}
    _export = lambda x, y: None
    command: Command = invoker.create_runner(_aliases=_aliases, _export=_export)
    command.inject(dict(XSH=xonsh_session))
    command([1, True, 3, 4])

def test_command_invoker(run_command, xonsh_session):
    def f(a:int, b:bool, c:str, /, *args,
          XSH,
          XGIT,
          stderr: IO[str],
          stdout: IO[str],
          stdin: IO[str],
          **kwargs):
        return  a, b, c, args, type(XSH), kwargs
    
    with run_command(f, [1, True, '3', 4],
                     expected=(1, True, '3', (4,), type(xonsh_session), {}),
                     expect_no_session_exception=False) as cmd_info:
        pass

def test_command_invoker_extra_kw(run_command, xonsh_session):
    def f(a:int, b:bool, c:str, /, *args,
          XSH: XonshSession,
          stderr: IO[str],
          stdout: IO[str],
          stdin: IO[str],
          **kwargs):
        return  a, b, c, args, type(XSH), kwargs.keys()
    with run_command(f, [1, True, '3', 4, '--extra', 'fun'],
                     expected=(1, True, '3', (4,), type(xonsh_session), {'extra'}),
                     expect_no_session_exception=False,
                     flags={'extra': 1}) as cmd_info:
        pass

def test_invoker_repr():
    def f(a:int, b:bool, c:str, /, *args, session: str, **kwargs):
        return  a, b, c, args, session, kwargs
    invoker = CommandInvoker(f, 'f', aliases={})
    assert repr(invoker) == '<CommandInvoker(f)(...)>'
