'''
Tests for `GitContext`.
'''

from typing import Any
from unittest.mock import NonCallableMock
from pathlib import Path

to_json: Any
from_json: Any


def test_context_loads(modules, sysdisplayhook):
    with modules('xontrib.xgit.context', 'xontrib.xgit.vars') as ((m_ctx, _), vars):
        assert m_ctx is not None

def test_context_simple(with_xgit, worktree, sysdisplayhook):
    def _t(*_, **__):
        import xontrib.xgit.context as ctx
        ctx = ctx._GitContext(worktree=worktree)
        assert ctx is not NonCallableMock
    with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.vars')

def test_context_json(with_xgit, worktree, git, sysdisplayhook, test_branch):
    def _t(*_, to_json, **__):
        import xontrib.xgit.context as ctx
        head = worktree.git('rev-parse', 'HEAD')
        branch = worktree.git('symbolic-ref', 'HEAD')
        ctx = ctx._GitContext(worktree=worktree)
        j = to_json(ctx, repository=worktree.repository)
        path = worktree.path
        expected = {
            'branch': branch,
            'path': '.',
            'commit': head,
            'worktree': {
                "repository": str(path / '.git'),
                'path': str(path),
                'repository_path': str(path / '.git'),
                'branch': branch,
                'commit': head,
                'locked': '',
                'prunable': '',
            },
        }
        assert j['worktree'] == expected['worktree']
        assert j == expected
    with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.to_json', 'xontrib.xgit.vars')
