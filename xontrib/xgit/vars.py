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
from typing import Optional

from xonsh.built_ins import XonshSession

import xontrib.xgit as xgit
from xontrib.xgit.types import (
    GitContext,
    GitObjectReference,
    GitObject,
    GitEntryKey, GitTreeEntry,
    _NoValue, _NO_VALUE,
)
from xontrib.xgit.proxy import (
    IdentityTargetAccessor, MappingAdapter, ObjectAdaptor, proxy, target,
    ModuleTargetAccessor, ProxyInitializer, BaseObjectAdaptor,
    MappingTargetAccessor,
    T, V,
)


def user_proxy(name: str, type: type[T], value: V|_NoValue=_NO_VALUE,
               adaptor: Optional[type[BaseObjectAdaptor]]=ObjectAdaptor,
               initializer: Optional[ProxyInitializer]=None) -> V|T:
    if initializer is None:
        initializer = lambda x: target(x, value)
    p = proxy(name, XSH.ctx, MappingTargetAccessor, ObjectAdaptor,
                 key=name,
                 type=type,
                 initializer=initializer,
            )
    return p


XSH: XonshSession = proxy('XSH', 'xonsh.built_ins', ModuleTargetAccessor,
                        key='XSH',
                        type=XonshSession,
                )
"""
The xonsh session object, via a `ContextLocal` stored in the xgit module
to allow persistence of the `ContextLocal` across reloads.
"""

XGIT: GitContext|None = user_proxy('XGIT', GitContext, None)
"""
Set the xgit context, making it available in the xonsh context,
and storing it in the context map.
"""

XGIT_CONTEXTS: dict[Path, GitContext] = user_proxy(
    'XGIT_CONTEXTS',
    dict,
    {},
    adaptor=MappingAdapter,
)
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""

XGIT_OBJECTS: dict[str, GitObject] = user_proxy(
    'XGIT_OBJECTS',
    dict,
    {},
    adaptor=MappingAdapter,
)
"""
A map from the hash of a git object to the object itself.
Stored here to persist across reloads.
"""

XGIT_ENTRIES: dict[GitEntryKey, GitTreeEntry] = user_proxy(
    'XGIT_ENTRIES',
    dict,
    {},
    adaptor=MappingAdapter,
)
"""
A map from the hash of a git object to the object itself.
Stored here to persist across reloads.
"""

XGIT_REFERENCES: dict[str, set[GitObjectReference]] = user_proxy(
    'XGIT_REFERENCES',
    dict,
    {},
    adaptor=MappingAdapter,
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
