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
import sys
from threading import RLock
from weakref import WeakKeyDictionary
from typing import (
    Callable, Mapping, MutableMapping, Optional, cast, Any, overload,
    Generic, TypeAlias, TypeVar
)

from xontrib.xgit.types import XGitProxy

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

class _NoValue:
    """A type for a marker for a value that is not passed in."""
    __match_args__ = ()
    def __repr__(self):
        return '_NO_VALUE'

_NO_VALUE = _NoValue()
"""A marker value to indicate that a value was not supplied"""

class TargetDescriptor(Generic[V, D, M]):
    """
    A reference to the target object for a proxy object.

    These follow the descriptor protocol, even though we're not
    using them as descriptors. This is because the descriptor
    protocol meets our needs and it's good to be consistent
    with something semi-familiar.

    The implementation of the descriptor protocol controls how the target object is stored
    and retrieved. Access to the object is provided by a separate `ObjectAdaptor`,
    with method names derived from corresponding dunder methods. The `ObjectAdaptor` methods
    provide access to the target object. They may be overridden to provide alternate access.

    T: The type of the target object.
    D: The type of the descriptor of the mapping. This is usually the mapping itself (M)
    M: The type of the mapping object.
    """
    mapping_descriptor: D
    name: str
    owner: XGitProxy
    default: V|_NoValue

    def __init__(self, mapping_descriptor: D, default: V|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None):
        self.mapping_descriptor = mapping_descriptor
        self.name = name or str(id(self))
        self.default = default

    @property
    def target(self) -> V:
        """
        Get the target object.
        """
        with _meta.lock:
            return self.__get__(self.owner, type(self.owner))
    @abstractmethod
    def __get__(self, obj: XGitProxy|None, objtype: type) -> V: ...
    @abstractmethod
    def __set__(self, obj, value: V): ...
    @abstractmethod
    def __delete__(self, obj: XGitProxy): ...

    def __set_name__(self, owner: XGitProxy, name: str):
        if hasattr(self, 'owner'):
            raise AttributeError("Can't use a descriptor more than one; create a separate instance.")
        self.owner = owner
        self.name = name

    @property
    def mapping(self) -> M:
        """
        Override this if the mapping decscriptor is not the mapping itself.
        """
        return cast(M, self.mapping_descriptor)

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        name = self.name
        return f'{cls}({name!r})'


class ObjectAdaptor(Generic[V]):
    """
    These methods parallel the dunder methods, implementing them for the proxy object.
    These don't need locking so long as the target is acquired just once
    and the target object is thread-safe.
    """
    descriptor: TargetDescriptor[V, Any, Any]
    def __init__(self: 'ObjectAdaptor', descriptor: TargetDescriptor[V, Any, Any]):
        self.descriptor = descriptor
    @property
    def target(self) -> V:
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

class AttributeAdapter(ObjectAdaptor[V]):
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

class MappingAdapter(MutableMapping[Any, V], ObjectAdaptor[V]):
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

class KeyedTargetDescriptor(TargetDescriptor[V, D, MM]):
    """
    A reference to the target object for a proxy object, with the
    ultimate target living in an attribute or key in the first-level target.
    """
    key: str
    def __init__(self, mapping_descriptor: D, key: str, default: V|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None):
        super().__init__(mapping_descriptor, default, name=name)
        self.key = key

class BaseMappingTargetDescriptor(KeyedTargetDescriptor[V, D, MM]):
    """
    A reference to the target object for a proxy object, with the target living in a Mapping.
    """
    key: str
    def __init__(self, mapping_descriptor: D, key: str, default: V|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None):
        super().__init__(mapping_descriptor, key, default, name=name)
    def __get__(self, _, objtype) -> V:
        try:
            return self.mapping[self.key]
        except KeyError:
            if self.default is _NO_VALUE:
                raise
            default = cast(V, self.default)
            return default

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


class Base2MappingTargetDescriptor(BaseMappingTargetDescriptor[V, MM, MM]):
    "Just constrains the two mapping types to be the same"
    pass


class MappingTargetDescriptor(Base2MappingTargetDescriptor[V, MutableMapping[str, V]]):
    pass


class ModuleTargetDescriptor(BaseMappingTargetDescriptor[V, str, MutableMapping[str, V]]):
    """
    A reference to a variable in a module.
    """
    @property
    def mapping(self) -> MutableMapping[str, V]:
        return sys.modules[self.mapping_descriptor].__dict__

    def __repr__ (self)-> str:
        return f'{{cls}}(sys.modules[{self.key}])'


class AttributeTargetDescriptor(TargetDescriptor[V, object, object]):
    """
    A reference to the target object for a proxy object, with the target living in an object and the keys being an  attribute..
    """
    attribute: str
    def __init__(self, mapping_descriptor: object, attribute: str, default: V|_NoValue=_NO_VALUE, /, *,
                    name: Optional[str]=None):
            super().__init__(mapping_descriptor, default, name=name)
            self.attribute = attribute

    def __get__(self, _, objtype) -> V:
        if self.default is _NO_VALUE:
            return getattr(self.mapping, self.attribute)
        default = cast(V, self.default)
        return getattr(self.mapping, self.attribute, default)

    def __set__(self, obj: XGitProxy, value: V):
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


class _ProxyMetadata:
    lock: RLock
    descriptors: WeakKeyDictionary[XGitProxy, TargetDescriptor]
    no_pass_through: set[str]
    def __init__(self):
        self.lock = RLock()
        self.descriptors = WeakKeyDictionary()
        self.no_pass_through = {'_target', '__class__', '__dict__', '__dir__', '__doc__', '__module__', '__weakref__'}

_meta = _ProxyMetadata()

def descriptor(proxy: XGitProxy, /) -> TargetDescriptor:
    """
    Get the descriptor for a proxy object.
    """
    return _meta.descriptors[proxy]

@overload
def target(proxy: XGitProxy[V], /) -> V: ...
@overload
def target(proxy: XGitProxy[V], value: V, /) -> None: ...
@overload
def target(proxy: XGitProxy[V], /, *, delete: bool) -> None: ...
def target(proxy: XGitProxy[V], value: _NoValue|V=_NO_VALUE, /, *, delete: bool=False) -> Any|None:
    """
    Get, set, or delete the target object for a proxy object.
    """
    d = descriptor(proxy)
    assert d is not None, f'No target descriptor for {proxy}'

    match value, delete:
        case _NoValue(), True:
            d.__delete__(proxy)
            del d.__get__
        case _NO_VALUE, _:
            return d.__get__(None, type(proxy))
        case _, _:
            _meta.descriptors[proxy] = value


class _XGitProxy(XGitProxy[V]):
    """
    A proxy for items managed in other contexts.
    """
    def __getitem__(self, name):
        with _meta.lock:
            t = cast(Mapping[str,V], target(self))
            return t[name]

    def __setitem__(self, name, value):
        with _meta.lock:
            t = cast(MutableMapping[str,V], target(self))
            t[name] = value

    def __delitem__(self, name):
        with _meta.lock:
            t = cast(MutableMapping[str,V], target(self))
            del t[name]

    def __setattr__(self, name: str, value):
        with _meta.lock:
            t = target(self)
            return setattr(t, name, value)

    def __getattr__(self, name):
        with _meta.lock:
            if name in _meta.no_pass_through:
                try:
                    return super().__getattribute__(name)
                except AttributeError:
                    d = descriptor(self)
                    return d.__get__(self, type(self))
            d = descriptor(self)
            return d.__get__(self, type(self))

    def __contains__(self, name):
        with _meta.lock:
            target = self._target
            return name in target

    def __hasattr__(self, name):
        with _meta.lock:
            target = self._target
            return hasattr(target, name)

    def __bool__(self):
        with _meta.lock:
            target = self._target
            return bool(target)

    def __str__(self):
        d = descriptor(self)
        name = d.name
        return str(f'{type(self).__name__}({name=!r}, target={self._target})')

ProxyInitializer: TypeAlias = Callable[[XGitProxy[V]],
                                       None|Callable[[XGitProxy[V]], None]]
"""
If a `ProxyInitializer` is provided to `proxy`, it will be called with the proxy object
during plugin initialization. The initializer can be used to set up the proxy object
for use in the plugin, creating the mapping object if necessary, and supplying an
initial value for the target object.

If the initializer returns a callable, that callable will be called when the plugin
is unloaded. This can be used to clean up any resources associated with the proxy object
or to restore the unloaded state.
"""

AdapterFactory: TypeAlias = Callable[[TargetDescriptor[V,D,M]], ObjectAdaptor[V]]
"""
A function that adapts a `TargetDescriptor` by wrapping it in an
`ObjectAdaptor`. This can be a class (such as `AttributeAdapter` or `MappingAdapter`)
or a factory function that returns an `ObjectAdaptor`.
"""

def proxy(name: str, descriptor: TargetDescriptor[V,D,M], adaptor: AdapterFactory[V, D, M], /,
          value_type: Optional[type[V]] = None,
          mapping_type: Optional[type[MM]] = None,
          instance_type: type[XGitProxy] = _XGitProxy,
          initializer: Optional[ProxyInitializer] = None,
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
    proxy = _XGitProxy()
    descriptor.__set_name__(proxy, name)
    _meta.descriptors[proxy] = descriptor
    return proxy
