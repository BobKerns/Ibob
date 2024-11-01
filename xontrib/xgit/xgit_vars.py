'''
Shared globals for xgit.
'''
from collections import defaultdict
from pathlib import Path
import sys

from xonsh.built_ins import XSH

from xontrib.xgit.xgit_types import (
    GitContext,
    GitObjectReference,
    GitObject,
)

XGIT: GitContext | None = None
"""
The current `GitContext` for the session,
or none if not in a git repository or worktree.
"""


def _set_xgit(xgit: GitContext | None) -> GitContext | None:
    """
    Set the xgit context, making it available in the xonsh context,
    and storing it in the context map.
    """
    global XGIT
    XSH.ctx["XGIT"] = XGIT = xgit
    if xgit is not None:
        XGIT_CONTEXTS[xgit.worktree or xgit.repository] = xgit
    return xgit


XGIT_CONTEXTS: dict[Path, GitContext] = {}
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""


XGIT_OBJECTS: dict[str, GitObject] = {}
"""
All the git entries we have seen.
"""


XGIT_REFERENCES: dict[str, set[GitObjectReference]] = defaultdict(set)
"""
A map to where an object is referenced.
"""


# Set up the notebook-style convenience history variables.

_xgit_counter = XSH.ctx.get("_xgit_counter", None) or iter(range(sys.maxsize))
_count: int = next(_xgit_counter)
