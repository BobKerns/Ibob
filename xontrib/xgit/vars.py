'''
Shared proxied globals for xgit.

This sets up proxies for values stored in the either:
- the user global context in the `XonshSession` object.
- the xgit module, for persistence across reloads.

(Or both).

The `XonshSession` object is stored in a `ContextLocal` in the xgit module,
permitting separate contexts for different contexts, e.g. with
different threads or asyncio tasks.
'''
from pathlib import Path
from threading import Lock
import sys

from extracontext import ContextLocal

from xonsh.built_ins import XonshSession
import xontrib.xgit as xgit
from xontrib.xgit.types import (
    GitContext,
    GitObjectReference,
    GitObject,
    _NoValue, _NO_VALUE,
)
from xontrib.xgit.proxy import (
    ContextLocalAccessor, IdentityTargetAccessor, MappingAdapter, meta, proxy, target,
    ModuleTargetAccessor, ObjectTargetAccessor,
    T, V,
)


def user_proxy(name: str, type: type[T], value: V|_NoValue=_NO_VALUE) -> V|T:
    def init_user_proxy(p):
        def on_xsh(xsh_proxy, xsh: XonshSession):
            target(p, xsh.env)
        meta(XSH).on_init(on_xsh)
    return proxy(name, None, IdentityTargetAccessor, MappingAdapter,
                 key='env',
                 type=type,
                 initializer=init_user_proxy
            )

def xgit_proxy(name: str, type: type[T], value: V|_NoValue=_NO_VALUE) -> V|T:
    return proxy(name, 'xontrib.xgit', ModuleTargetAccessor,
                 key=name,
                 type=type,
                 initializer=lambda p: target(p, value)
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

XSH: XonshSession = proxy('XSH', _CONTEXT, ContextLocalAccessor,
                        key='XSH',
                        type=XonshSession,
                )
"""
The xonsh session object, via a `ContextLocal` stored in the xgit module
to allow persistence of the `ContextLocal` across reloads.
"""

XGIT: GitContext|None = user_proxy('XGIT', GitContext)
"""
Set the xgit context, making it available in the xonsh context,
and storing it in the context map.
"""

XGIT_CONTEXTS: dict[Path, GitContext] = user_proxy(
    'XGIT_CONTEXTS',
    dict,
    {}
)
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""

XGIT_OBJECTS: dict[str, GitObject] = user_proxy(
    'XGIT_OBJECTS',
    dict,
    {}
)
"""
A map from the hash of a git object to the object itself.
Stored here to persist across reloads.
"""

XGIT_REFERENCES: dict[str, set[GitObjectReference]] = user_proxy(
    'XGIT_REFERENCES',
    dict,
    {}
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
