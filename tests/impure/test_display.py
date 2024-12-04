"""
Tests for the display module.
"""


def test_display_loads(modules):
    with modules('xontrib.xgit.display') as ((m_display,), vars):
        assert m_display is not None

def test_displayhook_events(with_xgit, modules, with_events, capsys):
    from xonsh.events import events
    from xontrib.xgit.display import events as display_events
    assert events is display_events

def test_displayhook_None(with_xgit,
                          modules,
                          xonsh_session,
                          capsys,
                          test_branch):
    from xontrib.xgit.display import _xgit_displayhook
    # XSH here to be found on the stack.
    XSH = with_xgit.XSH # noqa: F841
    _xgit_displayhook(None)
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""