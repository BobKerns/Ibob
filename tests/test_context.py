'''
Tests for `GitContext`.
'''

from typing import AnyStr, cast, Any
from unittest.mock import NonCallableMock

_GitContext: Any
to_json: Any
from_json: Any


def test_context_loads(modules, sysdisplayhook):
    with modules('xontrib.xgit.context', 'xontrib.xgit.vars') as ((m_ctx, _), vars):
        assert m_ctx is not None

def test_context_simple(with_xgit, sysdisplayhook):
    def _t(*_, _GitContext, **__):
        ctx = _GitContext()
        assert ctx is not NonCallableMock
    with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.vars')

def test_context_json(with_xgit, sysdisplayhook):
    def _t(*_, _GitContext, to_json, from_json, **__):
        ctx = _GitContext()
        ctx.commit = "ab35f88"
        ctx.branch = "fred"
        j = to_json(ctx, _GitContext)
        assert j == {
            'branch': 'fred',
            'common': '.git',
            'git_path': '.',
            'commit': 'ab35f88',
            'worktree': '.',
            'repository': '.git'
        }
    with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.to_json', 'xontrib.xgit.vars')
