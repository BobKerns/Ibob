"""
Proxy objects to access objects that live in other namespaces. Notable examples include:

* xonsh global namespace, accessed via the `XonshSession.ctx` attribute.
* The main module's namespace (`xontrib.xgit`), which survives reloads.
* A context variable namespace, accessed via the `ContextMap` or `ContextLocal` classes
  from the [`extracontext`(https://github.com/jsbueno/extracontext?tab=readme-ov-file)
  library.

  The [`extracontext`](https://github.com/jsbueno/extracontext?tab=readme-ov-file) library
  is a [PEP-567](https://peps.python.org/pep-0567/)-compliant implementation, with
  the advantage of working seamlessly with threads, asyncio tasks, and generators.

Both the namespace and the values within it are accessed through the descriptor and adaptor.
Thus, the descriptor may describe a module, or a dictionary stored in a variable in the
current global namespace. Accesses to attributes or items in the proxy object are
translated to accesses to the target object.

The adaptor controls how the target object is accessed. It provides methods that
parallel the dunder methods, such as `__getitem__` and `__setitem__`, and performs
the actual access to the target object on behalf of the proxy.

The `proxy` function creates a proxy object for values in another namespace. It takes
at a minimum a name for the proxy object, a descriptor for the target object, and an
adaptor that controls how the target object is accessed.

The descriptor locates the target object that holds the namespace. It may be a module
name, an object that holds the namespace, or the namespace itself. The descriptor
locates the namespace, and the adaptor provides the methods to access values stored
in the namespace. These can be attributes, values in a dictionary, items in a list,
or even methods on the target object.
"""

from abc import abstractmethod
from email.mime import base
import sys
from threading import RLock
from weakref import WeakKeyDictionary
from typing import (
    Callable, Literal, Mapping, MutableMapping, Optional, Protocol, cast, Any, overload,
    Generic, TypeAlias, TypeVar
)
from collections import deque

V = TypeVar('V')
"""
The type of object stored in the proxy object's target. This will typically be `Any`,
but may be more restrictive if the target object supports a more limited value type.
"""
D = TypeVar('D')
"""
The type of the descriptor of the mapping. This is usually the mapping itself (`M`),
in which case the `MM` type variable may be used to constrain the descriptor and
mapping to have the same type.

It may be other types, such as a string for a module name, or an object for an attribute.
"""
M = TypeVar('M')
"""
The type of the mapping object. This is usually a `MutableMapping`, but may be other types,
by supplying a suitable adaptor.
"""
MM = TypeVar('MM', bound=MutableMapping)

T = TypeVar('T')
"""
The type of the target object.
"""

class _NoValue:
    """A type for a marker for a value that is not passed in."""
    __match_args__ = ()
    def __repr__(self):
        return '_NO_VALUE'

_NO_VALUE = _NoValue()
"""A marker value to indicate that a value was not supplied"""

class TargetAccessor(Generic[D, M, T, V]):
    """
    A reference to the target object for a proxy object.

    These follow the descriptor protocol, even though we're not
    using them as descriptors. The descriptor protocol allows us
    to get, set, and delete the target object.
    
    For flexibility, we perform the access in two steps. We start
    with a descriptor (`D`) that locates an intermediate object where the
    target object is stored. This intermediate object may be a module,
    a dictionary, or an object, in which the target is stored. We call
    this the mapping (`M`).
    
    

    The implementation of the descriptor protocol controls how the target object is stored
    and retrieved. Access to the object is provided by a separate `ObjectAdaptor`,
    with method names derived from corresponding dunder methods. The `ObjectAdaptor` methods
    provide access to the target object. They may be overridden to provide alternate access.

    D: The type of the descriptor of the mapping. This is usually the mapping itself (M)
    M: The type of the mapping object.
    T: The type of the target object.
    V: The type of the value stored in the target object (usually Any).
    """
    descriptor: D
    name: str
    owner: 'XGitProxy[T, V]'
    default: T|_NoValue

    def __init__(self, descriptor: D, default: T|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None,
                 **kwargs):
        self.descriptor = descriptor
        self.name = name or str(id(self))
        self.default = default

    @property
    def target(self) -> T:
        """
        Get the target object.
        """
        with _meta.lock:
            return self.__get__(self.owner, type(self.owner))
        
    def __get__(self, obj: 'XGitProxy[T, V]|None', objtype: type) -> T: ...
    @abstractmethod
    def __set__(self, obj, value: T): ...
    @abstractmethod
    def __delete__(self, obj: 'XGitProxy[T, V]'): ...

    def __set_name__(self, owner: 'XGitProxy[T, V]', name: str):
        if hasattr(self, 'owner'):
            raise AttributeError("Can't use a descriptor more than once; create a separate instance.")
        self.owner = owner
        self.name = name

    @property
    def mapping(self) -> M:
        """
        Override this if the mapping decscriptor is not the mapping itself.
        """
        return cast(M, self.descriptor)

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        name = self.name
        return f'{cls}({name!r})'

AdaptorMethod: TypeAlias = Literal[
    'getitem', 'setitem', 'delitem', 'setattr', 'getattr', 'contains', 'hasattr', 'bool'
]

class BaseObjectAdaptor(Generic[T, V]):
    """
    These methods parallel the dunder methods, implementing them for the proxy object.
    These don't need locking so long as the target is acquired just once
    and the target object is thread-safe.
    """

    @property
    def target(self) -> T:
        d = self.__getattribute__('descriptor')
        return d.target

    def getitem(self, name):
        tm = cast(Mapping[str,V], self.target)
        if not hasattr(tm, '__getitem__'):
            raise TypeError(f'{tm} has no __getitem__ method')
        return tm[name]

    def setitem(self, name, value):
        tm = cast(MutableMapping[str,V], self.target)
        if not hasattr(tm, '__setitem__'):
            raise TypeError(f'{tm} has no __setitem__ method')
        tm[name] = value

    def delitem(self, name):
        tm = cast(MutableMapping[str,V], self.target)
        if not hasattr(tm, '__delitem__'):
            raise TypeError(f'{tm} has no __delitem__ method')
        del tm[name]

    def setattr(self, name: str, value):
        target = self.target
        if not hasattr(target, '__setattr__'):
            raise TypeError(f'{target} has no __setattr__ method')
        return setattr(target, name, value)

    def getattr(self, name):
        if name in _meta.no_pass_through:
            return super().__getattribute__(name)

        target = self.target
        if not hasattr(target, '__getattr__'):
            raise TypeError(f'{target} has no __getattr__ method')
        getattr(target, name)

    def contains(self, name):
        target = self.target
        return name in target

    def hasattr(self, name):
        target = self.target
        return hasattr(target, name)

    def bool(self):
        target = self.target
        return bool(target)

class ObjectAdaptor(BaseObjectAdaptor[T,V]):
    """
    Basic default `ObjectAdaptor` that provides transparent access to the target object.
    """

    descriptor: TargetAccessor[Any, Any, T, V]

    def __init__(self: 'ObjectAdaptor',
                 descriptor: TargetAccessor[Any, Any, T, V],
                 **kwargs):
        self.descriptor = descriptor

ProxyAction: TypeAlias = Literal['get', 'set', 'delete', 'bool']
"""
Flags indicating the action being undertaken at the time of proxy access.
"""
class AdaptorWrapperFn(Generic[V], Protocol):
    """
    A function that validates or perform other actions on the value being
    set or read from on the target object.
    """
    @overload
    @abstractmethod
    def __call__(self, value: None, action: Literal['delete'], method: AdaptorMethod, /) -> None: ...
    @overload
    @abstractmethod
    def __call__(self, value: bool, action: Literal['bool'], method: AdaptorMethod, /) -> bool: ...
    @overload
    @abstractmethod
    def __call__(self, value: V, action: ProxyAction, method: AdaptorMethod, /) -> V: ...
    @overload
    @abstractmethod
    def __call__(self, value: V|None|bool, action: ProxyAction, method: AdaptorMethod, /) -> V|None|bool: ...
    @abstractmethod
    def __call__(self, value: V|None|bool, action: ProxyAction, method: AdaptorMethod, /) -> V|None|bool: ...

class AdapterWrapper(ObjectAdaptor[T, V]):
    """
    This adaptor wraps another adaptor, allowing for additional operations
    to be performed on the target object.
    """
    base_adaptor: ObjectAdaptor[T, V]
    wrapper_fn: AdaptorWrapperFn[V]

    def __init__(self,
                 base_adaptor: ObjectAdaptor[T, V],
                wrapper_fn: AdaptorWrapperFn,
                **kwargs):
            self.base_adaptor = base_adaptor
            self.wrapper_fn = wrapper_fn

    @overload
    def _wrap(self, value: None, action: Literal['delete'], method: AdaptorMethod, /) -> None: ...
    @overload
    def _wrap(self, value: bool, action: Literal['bool'], method: AdaptorMethod, /) -> bool: ...
    @overload
    def _wrap(self, value: V, action: ProxyAction, method: AdaptorMethod, /) -> V: ...
    @overload
    def _wrap(self, value: V|bool|None, action: ProxyAction, method: AdaptorMethod, /) -> V|bool|None: ...
    def _wrap(self, value: V|bool|None, action: ProxyAction, method: AdaptorMethod, /) -> V|bool|None:
        return self.wrapper_fn(value, action, method)

    def getitem(self, name):
        return self._wrap(self.base_adaptor.getitem(name), 'get', 'getitem')

    def setitem(self, name, value):
        self.base_adaptor.setitem(name, self._wrap(value, 'set', 'setitem'))

    def delitem(self, name):
        self._wrap(None, 'delete', 'delitem')
        self.base_adaptor.delitem(name)

    def setattr(self, name, value):
        self.base_adaptor.setattr(name, self._wrap(value, 'set', 'setattr'))

    def getattr(self, name):
        return self._wrap(self.base_adaptor.getattr(name), 'get', 'getattr')

    def contains(self, name):
        return self.base_adaptor.contains(name)

    def hasattr(self, name):
        return self.base_adaptor.hasattr(name)

    def bool(self):
        return self.base_adaptor.bool()


class AttributeAdapter(ObjectAdaptor[T, V]):
    """
    This adaptor maps dictionary keys on the target object to attributes on the proxy object.
    """
    def getitem(self, name):
        return self.getattr(name)

    def setitem(self, name, value):
        self.setattr(name, value)

    def delitem(self, name):
        target = self.target
        if not hasattr(target, '__delattr__'):
            raise TypeError(f'{target} has no __delattr__ method')
        delattr(target, name)

    def contains(self, name):
        return self.hasattr(name)

class MappingAdapter(MutableMapping[Any, V], ObjectAdaptor[T, V]):
    """
    This adaptor maps dictionary or array keys on the proxy object
    to attributes on the target object.
    """
    def getattr(self, name):
        return self.getitem(name)

    def setattr(self, name, value):
        self.setitem(name, value)

    def delattr(self, name):
        self.delitem(name)

    def hasattr(self, name):
        return self.contains(name)


    def __iter__(self):
        return iter(self.target.__dict__)

class KeyedTargetAccessor(TargetAccessor[D, MM, T, V]):
    """
    A reference to the target object for a proxy object, with the
    ultimate target living in an attribute or key in the first-level target.
    """
    key: str
    def __init__(self,
                 descriptor: D,
                 key: str,
                 default: T|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None,
                 **kwargs):
        super().__init__(descriptor, default, name=name)
        self.key = key

class BaseMappingTargetAccessor(KeyedTargetAccessor[D, MM, T, V]):
    """
    A reference to the target object for a proxy object, with the target living in a Mapping.
    """
    key: str
    def __init__(self,
                 descriptor: D,
                 key: str,
                 default: T|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None,
                 **kwargs):
        super().__init__(descriptor, key, default, name=name)
    def __get__(self, _, objtype) -> T:
        try:
            return self.mapping[self.key]
        except KeyError:
            if self.default is _NO_VALUE:
                raise
            default = self.default
            return cast(T, default)

    def __set__(self, obj, value:V):
        match value, self.default:
            case _NoValue(),_NoValue():
                self.__delete__(obj)
            case _NoValue(), _:
                setattr(self.mapping, self.key, self.default)
            case _, _:
                setattr(self.mapping, self.key, value)

    def __delete__(self, _):
        del self.mapping[self.key]

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        return f'{cls}({self.name}[{self.key!r}])'


class Base2MappingTargetAccessor(BaseMappingTargetAccessor[MM, MM, T, V]):
    "Just constrains the two mapping types to be the same"
    pass


class MappingTargetAccessor(Base2MappingTargetAccessor[MutableMapping[str, V], T, V]):
    pass


class ModuleTargetAccessor(BaseMappingTargetAccessor[str, MutableMapping[str, V], T, V]):
    """
    A reference to a variable in a module.
    """
    @property
    def mapping(self) -> MutableMapping[str, V]:
        return sys.modules[self.descriptor].__dict__

    def __repr__ (self)-> str:
        return f'{{cls}}(sys.modules[{self.key}])'


class AttributeTargetAccessor(TargetAccessor[object, object, T, V]):
    """
    A reference to the target object for a proxy object, with the target living in an object and the keys being an  attribute..
    """
    attribute: str
    def __init__(self,
                mapping_descriptor: object,
                attribute: str,
                default: T|_NoValue=_NO_VALUE, /, *,
                name: Optional[str]=None,
                **kwargs):
            super().__init__(mapping_descriptor, default, name=name)
            self.attribute = attribute

    def __get__(self, _, objtype) -> T:
        if self.default is _NO_VALUE:
            return getattr(self.mapping, self.attribute)
        default = cast(T, self.default)
        return getattr(self.mapping, self.attribute, default)

    def __set__(self, obj: 'XGitProxy[T, V]', value: V):
        match value, self.default:
            case _NoValue(),_NoValue():
                self.__delete__(obj)
            case _NoValue(), _:
                setattr(self.mapping, self.attribute, self.default)
            case _, _:
                setattr(self.mapping, self.attribute, value)

    def __delete__(self, _):
        delattr(self.mapping, self.attribute)

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        return f'{{cls}}(.{self.name}.{self.attribute})'


class XGitProxy(Generic[T,V]):
    """
    A proxy for items managed in other contexts.
    """
    def __getitem__(self, name):
        with _meta.lock:
            return adaptor(self).getitem(name)

    def __setitem__(self, name, value):
        with _meta.lock:
            adaptor(self).setitem(name, value)

    def __delitem__(self, name):
        with _meta.lock:
            adaptor(self).delitem(name)

    def __setattr__(self, name: str, value):
        with _meta.lock:
            adaptor(self).setattr(name, value)

    def __getattr__(self, name):
        with _meta.lock:
            if name in _meta.no_pass_through:
                try:
                    return super().__getattribute__(name)
                except AttributeError:
                    pass
            return adaptor(self).getattr(name)

    def __contains__(self, name):
        with _meta.lock:
            return adaptor(self).contains(name)

    def __hasattr__(self, name):
        with _meta.lock:
            return adaptor(self).hasattr(name)

    def __bool__(self):
        with _meta.lock:
            return adaptor(self).bool()

    def __str__(self):
        d = descriptor(self)
        name = d.name
        return str(f'{type(self).__name__}({name=!r}, target={self._target})')

ProxyDeinitializer: TypeAlias = Callable[[XGitProxy[T, V]], None]
"""
A function returned from a `ProxyInitializer` that cleans up resources associated with the proxy object
on plugin unload.

"""

ProxyInitializer: TypeAlias = Callable[[XGitProxy[T, V]], ProxyDeinitializer|None]
"""
If a `ProxyInitializer` is provided to `proxy`, it will be called with the proxy object
during plugin initialization. The initializer can be used to set up the proxy object
for use in the plugin, creating the mapping object if necessary, and supplying an
initial value for the target object.

If the initializer returns a callable, that callable will be called when the plugin
is unloaded. This can be used to clean up any resources associated with the proxy object
or to restore the unloaded state.
"""

class TargetAccessorFactory(Generic[D, M, T, V], Protocol):
    """
    A factory function that creates a `TargetDescriptor` object.
    """
    def __call__(self, descriptor: D, **kwargs) -> TargetAccessor[D,M, T, V]: ...
    
class AdapterFactory(Generic[D, M, T, V], Protocol):
    """
    A function that adapts a `TargetDescriptor` by wrapping it in an
    `ObjectAdaptor`. This can be a class (such as `AttributeAdapter` or `MappingAdapter`)
    or a factory function that returns an `ObjectAdaptor`.
    """
    def __call__(self, descriptor: TargetAccessor[D,M, T, V], **kwargs) -> ObjectAdaptor[T, V]: ...  
    

def proxy(name: str,
          namespace: Any,
          descriptor: TargetAccessorFactory[D,M, T, V], 
          adaptor: AdapterFactory[D, M, T, V], /,
          value_type: Optional[type[V]] = None,
          mapping_type: Optional[type[MM]] = None,
          instance_type: type[XGitProxy[T, V]] = XGitProxy[T, V],
          initializer: Optional[ProxyInitializer] = None,
          **kwargs
    ) -> XGitProxy:
    """
    Create a proxy for values in another namespace.

    Both the namespace and the values within it are accessed through the descriptor and adaptor.
    Thus, the descriptor may describe a module, or a dictionary stored in a variable in the
    current global namespace. Accesses to attributes or items in the proxy object are
    translated to accesses to the target object.

    The adaptor controls how the target object is accessed. It provides methods that
    parallel the dunder methods, such as `__getitem__` and `__setitem__`, and performs
    the actual access to the target object on behalf of the proxy.
    """
    proxy = instance_type() 
    d = descriptor(namespace, **kwargs)
    d.__set_name__(proxy, name)
    _meta.descriptors[proxy] = d
    _meta.adaptors[proxy] = adaptor(d, **kwargs)
    if initializer is not None:
        _meta.initializers[proxy] = initializer
    return proxy

class _ProxyMetadata:
    lock: RLock
    descriptors: WeakKeyDictionary[XGitProxy, TargetAccessor]
    adaptors: WeakKeyDictionary[XGitProxy, ObjectAdaptor]
    initializers: WeakKeyDictionary[XGitProxy, ProxyInitializer]
    deinitializers: deque[ProxyDeinitializer]
    no_pass_through: set[str]
    def __init__(self):
        self.lock = RLock()
        self.descriptors = WeakKeyDictionary()
        self.adaptors = WeakKeyDictionary()
        self.initializers = WeakKeyDictionary()
        self.descriptors = WeakKeyDictionary()
        self.deinitializers = deque()
        self.no_pass_through = {'_target', '__class__', '__dict__', '__dir__', '__doc__', '__module__', '__weakref__'}


    def descriptor(self, proxy: 'XGitProxy[T, V]', /) -> TargetAccessor[object,object,T,V]:
        """
        Get the descriptor for a proxy object.
        """
        return self.descriptors[proxy]

    def adaptor(self, proxy: 'XGitProxy[T,V]', /) -> ObjectAdaptor[T,V]:
        """
        Get the adaptor for a proxy object.
        """
        return self.adaptors[proxy]

    def target(self, proxy: 'XGitProxy[T, V]', value: _NoValue|T=_NO_VALUE, /, *, delete: bool=False) -> Any|None:
        """
        Get, set, or delete the target object for a proxy object.
        """
        d = self.descriptor(proxy)
        assert d is not None, f'No target descriptor for {proxy}'

        match value, delete:
            case _NoValue(), True:
                d.__delete__(proxy)
                del d.__get__
            case _NO_VALUE, _:
                return d.__get__(None, type(proxy))
            case _, _:
                self.descriptors[proxy] = value


def descriptor(proxy: 'XGitProxy[T, V]', /) -> TargetAccessor[object, object, T, V]:
    """
    Get the descriptor for a proxy object.
    """
    return _meta.descriptor(proxy)

def adaptor(proxy: 'XGitProxy[T, V]', /) -> ObjectAdaptor[T, V]:
    """
    Get the adaptor for a proxy object.
    """
    return _meta.adaptor(proxy)
_adaptor = adaptor

@overload
def target(proxy: 'XGitProxy[T, V]', /) -> T: ...
@overload
def target(proxy: 'XGitProxy[T, V]', value: T, /) -> None: ...
@overload
def target(proxy: 'XGitProxy[T, V]', /, *, delete: bool) -> None: ...
def target(proxy: 'XGitProxy[T, V]', value: _NoValue|T=_NO_VALUE, /, *, delete: bool=False) -> T|None:
    """
    Get, set, or delete the target object for a proxy object.
    """
    return _meta.target(proxy, value, delete=delete)
_meta = _ProxyMetadata()