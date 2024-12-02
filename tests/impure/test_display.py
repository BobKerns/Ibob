"""
Tests for the display module.
"""

import re
from typing import Any, cast
_xgit_displayhook: Any

def test_display_loads(modules):
    with modules('xontrib.xgit.display') as ((m_display,), vars):
        assert m_display is not None

def test_displayhook_events(with_xgit, modules, with_events, capsys):
    from xonsh.events import events
    from xontrib.xgit.display import events as display_events
    assert events is display_events

def test_displayhook_simple(xonsh_session,
                            with_xgit,
                            modules,
                            sysdisplayhook,
                            capsys,
                            test_branch):
    XSH = with_xgit.XSH
    _events = __import__('xonsh.events').events.events
    with modules('xontrib.xgit.display') as ((mod,), kwargs):
        _events2 = mod.__dict__['events']
        assert _events is _events2
        #assert len(_events.on_xgit_predisplay) > 0
        _xgit_displayhook(42)
    out = capsys.readouterr()
    text = out.out
    assert xonsh_session.env.get('XGIT_ENABLE_NOTEBOOK_HISTORY')
    assert re.match(r'_\d+: 42', text), f"Expected _<number>: 42, got: {text}"
    assert out.err == ""

def test_displayhook_None(with_xgit,
                          modules,
                          xonsh_session,
                          capsys,
                          test_branch):
    from xontrib.xgit.display import _xgit_displayhook
    XSH = with_xgit.XSH # Found here on the stack.
    _xgit_displayhook(None)
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""