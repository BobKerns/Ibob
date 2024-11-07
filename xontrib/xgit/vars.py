'''
Shared proxied globals for xgit.

This sets up proxies for values stored in the either:
- the user global context in the `XonshSession` object.
- the xgit module, for persistence across reloads.

(Or both).

The `XonshSession` object is stored in a `ContextVar` in the xgit module,
permitting separate contexts for different contexts, e.g. with
different threads or asyncio tasks.
'''
from pathlib import Path
from threading import Lock
from typing import (
     Optional,
)
from functools import wraps
import sys

from extracontext import ContextLocal

from xonsh.built_ins import XonshSession
import xontrib.xgit as xgit
from xontrib.xgit.types import (
    GitContext,
    GitObjectReference,
    GitObject,
)
from xontrib.xgit.proxy import (
    proxy, target,
    ModuleTargetAccessor,
)

_CONTEXT = proxy('_CONTEXT', 'xontrib.xgit', ModuleTargetAccessor,
                 key='_CONTEXT',
                 initializer=lambda p: target(p, ContextLocal())
                 )
"""
We store a `ContextLocal` object in the xgit module, to allow persistence + session separation.

xonsh does not currently support multiple sessions in the same process, notably the `XSH`
global variable. But to avoid future problems, let's attempt to be thread safe.

Note that the `extracontext` module handles async tasks and generators, avoiding the issue
with threading.ContextVar, which is not inherited to new threads.
"""



if 0:
    XSH: XonshSession = context_var_proxy('_context')
    """
    The xonsh session object, via a `ContextVar` stored in the xgit module
    to allow persistence of the `ContextVariable` across reloads.
    """

def _set_xgit(value: Optional[GitContext | None]=None, name: Optional[str]=None):
    """
    Set the xgit context, making it available in the xonsh context,
    and storing it in the context map.
    """
    name = name or 'XGIT'
    to_user(name)(value)
    if value is not None:
        # Store the context in the context map.
        XGIT_CONTEXTS[value.worktree or value.repository] = value
    #return value``

XGIT: GitContext|None = user_proxy('XGIT',
    to_target=_set_xgit,
    #value=lambda: None,
)

XGIT_CONTEXTS: dict[Path, GitContext] = user_proxy(
    'XGIT_CONTEXTS',
    #value=lambda: {}
)
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""
_XGIT_OBJECTS: dict[str, GitObject] = xgit_proxy('_XGIT_OBJECTS',
#                                         value=lambda: defaultdict(xo._GitObject) # type: ignore
)
"""
A map from the hash of a git object to the object itself.
Stored here to persist across reloads.
"""

XGIT_OBJECTS: dict[str, GitObject] = user_proxy(
    'XGIT_OBJECTS',
#    value=lambda: _XGIT_OBJECTS._target # type: ignore
)

"""
A map from the hash of a git object to the object itself.
This persists across reloads and between sessions.
"""

XGIT_REFERENCES: dict[str, set[GitObjectReference]] = user_proxy('XGIT_REFERENCES',
#                                                                 value=lambda: defaultdict(set)
)
"""
A map to where an object is referenced.
"""

_count_lock = Lock()
# Set up the notebook-style convenience history variables.
def _xgit_count():
    """
    Set up and use the counter for notebook-style history.
    """
    with _count_lock:
        counter = xgit.__dict__.get("_xgit_counter", None)
        if not counter:
            counter = iter(range(1, sys.maxsize))
            xgit.__dict__["_xgit_counter"] = counter
        return next(counter)

_xgit_version: str = ""
def xgit_version():
    """
    Return the version of xgit.
    """
    global _xgit_version
    if _xgit_version:
        return _xgit_version
    from importlib.metadata import version
    _xgit_version = version("xontrib-xgit")
    return _xgit_version
