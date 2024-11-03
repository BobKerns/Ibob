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
from collections import defaultdict
from pathlib import Path
from contextvars import ContextVar, Token
from re import M
from threading import Lock, RLock
from tkinter import NO
from typing import (
    Any, Callable, Optional, cast, Protocol, overload,
    Sequence, Mapping, MutableMapping, TypeAlias, Literal,
    Generic, TypeVar,
)
from functools import wraps
import sys

from extracontext import ContextLocal

from xonsh.built_ins import XonshSession
import xontrib.xgit as xgit
from xontrib.xgit.xgit_types import (
    GitContext,
    GitObjectReference,
    GitObject,
    XGitProxy,
)
from xontrib.xgit import xgit_objects as xo
#_GitObject: GitObject

if '_context' in xgit.__dict__:
    _context = ContextLocal()
else:
    _context = ContextLocal()
    xgit.__dict__['_context'] = _context
    
T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)

class MappingFn(Generic[T], Protocol):
    def __call__(self) -> MutableMapping[str,T]: ...

class FromFn(Generic[T_co], Protocol):
    def __call__(self) -> T_co: ...    

class MkFromFn(Generic[T_co],Protocol):
    def __call__(self, name: str) -> FromFn[T_co]: ...
    
class ToFn(Generic[T_contra], Protocol):
    def __call__(self, value: Optional[T_contra]=None): ...
    
class MkToFn(Generic[T_contra], Protocol):
    def __call__(self, name: str, *args, **kwargs) -> ToFn[T_contra]: ...
    
class DelFn(Generic[T_co], Protocol):
    def __call__(self) -> None: ...
    
class MkDelFn(Generic[T_co], Protocol):
    def __call__(self, name: str) -> DelFn[T_co]: ...
    
class ValueFn(Generic[T_co],Protocol):
    def __call__(self) -> T_co: ...

_proxy_lock = RLock()
def proxy[T](name: str, *,
          from_target: FromFn[T],
          to_target: ToFn[T],
          del_target: DelFn[T],
          value: Optional[ValueFn[T]|T]=None,
          no_pass_through: Sequence[str]=('_target', '_context', '__getattr__', '__setattr__'),
          ) -> T:
    """
    Create a proxy for values kept in other contexts.

    These are often stored in the top-level module (xgit)  for persistence
    across reloading.

    Arguments:
    - from_target: a function that returns the target context.
    - to_target: a function to call to initialize or set.
            This should take 0 or 1 arguments.
    - del_target: a function to call to delete the target.
    - value: a function that returns the value to set if the target is None.

    Returns:
    - a proxy object that will call the target context when accessed.

    To change the target, set the `_target` attribute of the proxy.
    This has the same effect as an assignment would, but works through the proxy.

    You can also delete the target by deleting the `_target` attribute. This will
    delete the target in the context, but not the proxy itself.
    """
    class _XGitProxy(XGitProxy[T]):
        """
        A proxy for the xgit context.
        """
        @property
        def _target(self):
            with _proxy_lock:
                target = from_target()
                if target is None:
                    if callable(value):
                        to_target(value())
                    else:
                        to_target()
                target = from_target()
                return target
            
        @_target.setter
        def _target(self, value):
            to_target(value)
            
        @_target.deleter
        def _target(self):
            if del_target:
                del_target()
            else:
                to_target(cast(T,None))
                
        def __getitem__(self, name):
            with _proxy_lock:
                target = cast(Mapping[str,T],self._target)
                return target[name]
            
        def __setitem__(self, name, value):
            with _proxy_lock:
                target = cast(MutableMapping[str,T], self._target)
                target[name] = value
                
        def __setattr__(self, name: str, value):
            with _proxy_lock:
                if name == '_target':
                    return super().__setattr__(name, value)
                target = self._target
                return setattr(target, name, value)
            
        def __getattr__(self, name):
            with _proxy_lock:
                if name in no_pass_through:
                    try:
                        return super().__getattribute__(name)
                    except AttributeError:
                        nonlocal value
                        if callable(value):
                            value = value()
                        raise Exception(f'Error getting {name}, returning {value}')
                        return None
                target = self._target
                return getattr(target, name)
            
        def __contains__(self, name):
            with _proxy_lock:
                target = self._target
                return name in target
            
        def __hasattr__(self, name):
            with _proxy_lock:
                target = self._target
                return hasattr(target, name)
            
        def __bool__(self):
            with _proxy_lock:
                target = self._target
                return bool(target)
            
        def __str__(self):
            try:
                target = self._target
            except Exception as e:
                target = f'Error: {e}'
            return str(f'{type(self).__name__}({name=!r}, target={self._target})')
        

    return cast(T, _XGitProxy())


def proxy_access[T](
    mapper: MappingFn[T]
    ) -> tuple[MkFromFn[T], MkToFn[T], MkDelFn[T]]:
    def from_fn(name: str) -> FromFn[T]:
        """
        Get a value from the xgit module to allow persistence across reloads.
        """
        @wraps(from_fn)
        def wrapper() -> T:
            m = mapper()
            return m[name]
        return wrapper


    def to_fn(name: str, value: Optional[Callable[[], T]|T]=None) -> ToFn[T]:
        """
        Set a value in the xgit module to allow persistence across reloads.
        """
        if callable(value):
            value = value()
        @wraps(to_fn)
        def wrapper(value=value):
            m = mapper()
            if name not in m:
                if callable(value):
                    value = value()
                value = cast(T, value)
                m[name] = value
        return wrapper

    def del_fn(name: str) -> DelFn[T]:
        """
        Delete a value from the xgit module.
        """
        @wraps(del_fn)
        def wrapper():
            del xgit.__dict__[name]
        return wrapper
    return from_fn, to_fn, del_fn

from_user, to_user, del_user = proxy_access(
    lambda: XSH.ctx
)
from_xgit, to_xgit, del_xgit = proxy_access(
    lambda: xgit.__dict__
)

def user_proxy[T](name: str, *,
                from_target: Optional[FromFn[T]]=None,
                to_target: Optional[ToFn[T]]=None,
                del_target: Optional[DelFn[T]]=None,
                value: Optional[ValueFn[T]|T]=None
               ) -> T:
    """
    Create a proxy for values kept in the user context.
    """
    from_target = from_target or from_user(name)
    return proxy(
        name,
        from_target=from_target or from_user(name),
        to_target=to_target or to_user(name, value),
        del_target=del_target or del_user(name),
        value=value,
    )

def xgit_proxy[T](name: str, *,
                from_target: Optional[FromFn[T]]=None,
                to_target: Optional[ToFn[T]]=None,
                del_target: Optional[DelFn[T]]=None,
                value: Optional[ValueFn[T]|T]=None
               ) -> T:
    """
    Create a proxy for values kept in the xgit context.
    """
    return cast(T, proxy(
        from_target=from_target or from_xgit(name),
        to_target=to_target or to_xgit(name, value),
        del_target=del_target or del_xgit(name),
        name=name,
    ))


never_set_token = (None, None)
def context_var_proxy[T](name: str, value: T|tuple[None, None]=never_set_token) -> T:
    """
    Create a proxy for values kept in a context variable.
    """
    outer_value = value
    def inner_value():
        cv = ContextVar(name)
        if value is never_set_token:
            pass
        elif callable(outer_value):
            cv.set(outer_value())
        else:
            cv.set(outer_value)
        return cv

    var_proxy: ContextVar = xgit_proxy(name, value=inner_value)
    token = never_set_token
    def get_var():
        return var_proxy.get()
    
    def set_var(value=value):
        nonlocal token
        if token is never_set_token:
            if value is not never_set_token:
                if callable(value):
                    value = value()
                token = var_proxy.set(value)
        elif value is never_set_token:
            var_proxy.reset(cast(Token[T],token))
            token = never_set_token
        else:
            var_proxy.set(value)
        return var_proxy
    
    def del_var():
        nonlocal token
        if token is not never_set_token:
            var_proxy.reset(cast(Token[T], token))
            token = never_set_token
    # Until there's a way to make ContextVar objects inherit to
    # new threads spawned from this one, 
    return xgit_proxy(name)
    return proxy(
        from_target=get_var,
        to_target=set_var,
        del_target=del_var,
        value=lambda: var_proxy,
        name=name,
    )

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
    #return value

XGIT: GitContext|None = user_proxy('XGIT',
    to_target=_set_xgit,
    value=lambda: None,
)

XGIT_CONTEXTS: dict[Path, GitContext] = user_proxy(
    'XGIT_CONTEXTS',
    value=lambda: {})
"""
A map of git contexts by worktree, or by repository if the worktree is not available.

This allows us to switch between worktrees without losing context of what we were
looking at in each one.
"""
_XGIT_OBJECTS: dict[str, GitObject] = xgit_proxy('_XGIT_OBJECTS',
                                                 value=lambda: defaultdict(xo._GitObject) # type: ignore
)
"""
A map from the hash of a git object to the object itself.
Stored here to persist across reloads.
"""

XGIT_OBJECTS: dict[str, GitObject] = user_proxy(
    'XGIT_OBJECTS',
    value=lambda: _XGIT_OBJECTS._target # type: ignore
)

"""
A map from the hash of a git object to the object itself.
This persists across reloads and between sessions.
"""

XGIT_REFERENCES: dict[str, set[GitObjectReference]] = user_proxy('XGIT_REFERENCES',
                                                                 value=lambda: defaultdict(set)
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


NoValue: TypeAlias = tuple[Literal["NoValue"]]
_NO_VALUE = ("NoValue",)

def target[T](proxy: XGitProxy[T]|T, value: T|NoValue=_NO_VALUE) -> T:
    """
    Get the target of a proxy.
    """
    if value is _NO_VALUE:
        return cast(XGitProxy[T], proxy)._target
    value = cast(T,value)
    cast(XGitProxy[T], proxy)._target = value
    return value

def del_target(proxy: XGitProxy[Any]|Any):
    """
    Delete the target of a proxy.
    """
    del cast(XGitProxy[Any], proxy)._target