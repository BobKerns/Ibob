"""
Tests for the display module.
"""

from xontrib.xgit.display import _xgit_displayhook

def test_displayhook_simple(with_xgit, capsys):
    def _t(*_, **__):
        _xgit_displayhook(42)
        out = capsys.readouterr()
        assert out.out == "42\n"
        assert out.err == ""
    with_xgit(_t)

def test_displayhook_None(with_xgit, capsys):
    def _t(*_, **__):
        _xgit_displayhook(None)
        out = capsys.readouterr()
        assert out.out == "None\n"
        assert out.err == ""
    with_xgit(_t)