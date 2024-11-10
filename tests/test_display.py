"""
Tests for the display module.
"""

import re
from xontrib.xgit.display import _xgit_displayhook

def test_displayhook_simple(with_xgit, capsys):
    def _t(*_, **__):
        _xgit_displayhook(42)
        out = capsys.readouterr()
        text = out.out
        assert re.match(r'_\d+: 42', text)
        assert out.err == ""
    with_xgit(_t)

def test_displayhook_None(with_xgit, capsys):
    def _t(*_, **__):
        _xgit_displayhook(None)
        out = capsys.readouterr()
        assert out.out == ""
        assert out.err == ""
    with_xgit(_t)