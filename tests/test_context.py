'''
Tests for `GitContext`.
'''

from typing import AnyStr, cast, Any
from unittest.mock import NonCallableMock

_GitContext: Any
to_json: Any
from_json: Any


def test_context_loads(modules, sysdisplayhook):
    with modules('xontrib.xgit.context') as ((m_ctx,), vars):
        assert m_ctx is not None

def test_context_simple(modules, sysdisplayhook):
    with modules('xontrib.xgit.context') as _:
        ctx = _GitContext()
        assert ctx is not NonCallableMock

def test_context_json(modules, sysdisplayhook):
    with modules('xontrib.xgit.context', 'xontrib.xgit.to_json') as ((m_ctx, m_to_json), vars):
        ctx = _GitContext()
        ctx.commit = "ab35f88"
        assert ctx.commit == "ab35f88"
        j = to_json(ctx, _GitContext)

        assert j == to_json(from_json(j, _GitContext), _GitContext)
