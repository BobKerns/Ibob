"""
Tests for the display module.
"""

import re
from typing import Any
_xgit_displayhook: Any

def test_display_loads(modules):
    with modules('xontrib.xgit.display') as ((m_display,), vars):
        assert m_display is not None

def test_displayhook_events(with_xgit, modules, with_events, capsys):
    def _t0(*_, **__):
        with modules('xontrib.xgit.display') as ((mod,), kwargs):
            pass
    def _t(*_, **__):
        with modules('xontrib.xgit.display') as ((mod,), kwargs):
            events = mod.__dict__['events']
            assert len(events.on_xgit_predisplay) > 0

    with_xgit(_t0)
    with_xgit(_t)

def test_displayhook_simple(xonsh_session,
                            with_xgit,
                            modules,
                            sysdisplayhook,
                            capsys,
                            test_branch):
    #import sys
    #for k in list(sys.modules.keys()):
    #    if k.startswith('xontrib.xgit'):
    #        del sys.modules[k]
    def _t(*_, **__):
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
    with_xgit(_t)

def test_displayhook_None(with_xgit,
                          modules,
                          capsys,
                          test_branch):
    def _t(*_, **__):
        with modules('xontrib.xgit.display'):
            _xgit_displayhook(None)
        out = capsys.readouterr()
        assert out.out == ""
        assert out.err == ""
    with_xgit(_t)