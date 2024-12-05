'''
Tests for `GitContext`.
'''

from typing import Any, cast
from unittest.mock import NonCallableMock

to_json: Any
from_json: Any


def test_context_loads(sysdisplayhook):
    from xontrib.xgit.context import _GitContext
    assert _GitContext is not None

def test_context_simple(with_xgit, f_worktree, sysdisplayhook):
    import xontrib.xgit.context as ctx
    worktree = f_worktree.worktree
    ctx = ctx._GitContext(worktree.repository.context.session, worktree=worktree)
    assert ctx is not NonCallableMock

def test_context_json(with_xgit,
                      f_worktree,
                      f_XGIT,
                      f_git,
                      sysdisplayhook,
                      ):
    from xontrib.xgit.to_json import to_json
    worktree = f_worktree.worktree
    head = worktree.rev_parse('HEAD')
    branch = worktree.symbolic_ref('HEAD')
    ctx = f_XGIT
    ctx.worktree=worktree
    ctx.branch = branch
    ctx.commit = head
    j = to_json(ctx, repository=worktree.repository)
    loc = worktree.location
    expected = {
        'branch': branch,
        'path': '.',
        'commit': head,
        'worktree': {
            "repository": str(loc / '.git'),
            'path': str(worktree.path),
            'repository_path': str(loc / '.git'),
            'branch': branch,
            'commit': head,
            'locked': '',
            'prunable': '',
        },
    }
    assert isinstance(j, dict)
    j = cast(dict, j)
    assert j['worktree'] == expected['worktree']
    assert j == expected