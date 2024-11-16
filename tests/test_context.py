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

def test_context_json(with_xgit, sysdisplayhook, test_branch):
    def _t(*_, _GitContext, to_json, from_json, _run_text, **__):
        ref = f'refs/heads/{test_branch}'
        head = _run_text(['git', 'rev-parse', 'HEAD'])
        ctx = _GitContext()
        ctx.commit = head
        ctx.branch = ref
        j = to_json(ctx, _GitContext)
        assert j == {
            'branch': ref,
            'common': '.git',
            'git_path': '.',
            'commit': head,
            'worktree': '.',
            'repository': '.git'
        }
    with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.to_json', 'xontrib.xgit.vars')
