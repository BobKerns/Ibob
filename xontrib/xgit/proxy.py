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
from extracontext import ContextLocal, ContextMap
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

K = TypeVar('K')
"""
The type of the key used to access the target object.
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
        with ProxyMetadata.lock:
            return self.__get__(self.owner, type(self.owner))

    @target.setter
    def target(self, value: T):
        """
        Set the target object.
        """
        with ProxyMetadata.lock:
            self.__set__(self.owner, value)

    @target.deleter
    def target(self):
        """
        Delete the target object.
        """
        with ProxyMetadata.lock:
            self.__delete__(self.owner)

    @abstractmethod
    def __get__(self, obj: 'XGitProxy[T, V]', objtype: type) -> T: ...

    @abstractmethod
    def __set__(self, obj: 'XGitProxy[T,V]', value: T): ...

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


class IdentityTargetAccessor(TargetAccessor[T, T, T, V]):
    """
    A reference to the target object for a proxy object, with the target being given directly.
    """
    def __get__(self, _: 'XGitProxy[T,V]', objtype) -> T:
        return self.descriptor

    def __set__(self, _: 'XGitProxy[T,V]', value: T):
        self.descriptor = value

    def __delete__(self, _):
        del self.descriptor

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
        if name in ProxyMetadata._no_pass_through:
            return super().__getattribute__(name)
        target = self.target
        return  getattr(target, name)

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

    def __init__(self,
                 descriptor: TargetAccessor[Any, Any, T, V],
                 **kwargs):
        setattr(self, 'descriptor', descriptor)


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


class AdaptorWrapper(ObjectAdaptor[T, V]):
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


class KeyedTargetAccessor(Generic[D, K, M, T, V], TargetAccessor[D, M, T, V]):
    """
    A reference to the target object for a proxy object, with the
    ultimate target living in an attribute or key in the first-level target.
    """
    key: K
    def __init__(self,
                 descriptor: D,
                 key: K,
                 default: T|_NoValue=_NO_VALUE, /, *,
                 name: Optional[str]=None,
                 **kwargs):
        super().__init__(descriptor, default, name=name)
        self.key = key


class BaseMappingTargetAccessor(KeyedTargetAccessor[D, K, MM, T, V]):
    """
    A reference to the target object for a proxy object, with the target living in a Mapping.
    """
    def __init__(self,
                 descriptor: D,
                 /, *,
                 key: K,
                 default: T|_NoValue=_NO_VALUE,
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

    def __set__(self, obj, value:T):
        match value, self.default:
            case _NoValue(),_NoValue():
                self.__delete__(obj)
            case _NoValue(), _:
                self.mapping[self.key] = self.default
            case _, _:
                self.mapping[self.key] = value

    def __delete__(self, _):
        del self.mapping[self.key]

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        return f'{cls}({self.name}[{self.key!r}])'


class Base2MappingTargetAccessor(BaseMappingTargetAccessor[MM, K, MM, T, V]):
    "Just constrains the two mapping types to be the same"
    pass


class MappingTargetAccessor(Base2MappingTargetAccessor[MutableMapping[K, V], K, T, V]):
    pass


class ObjectTargetAccessor(KeyedTargetAccessor[D, str, M, T, V]):
    """
    A reference to the target object for a proxy object, with the target living in an attribute
    on an object..
    """
    key: str
    def __init__(self,
                 descriptor: D,
                 /, *,
                 key: str,
                 default: T|_NoValue=_NO_VALUE,
                 name: Optional[str]=None,
                 **kwargs):
        super().__init__(descriptor, key, default, name=name)
    def __get__(self, _, objtype) -> T:
        try:
            return getattr(self.mapping, self.key)
        except AttributeError:
            if self.default is _NO_VALUE:
                raise
            default = cast(T, self.default)
            self.__set__(objtype, default)
            return default

    def __set__(self, obj, value:T):
        match value, self.default:
            case _NoValue(),_NoValue():
                self.__delete__(obj)
            case _NoValue(), _:
                setattr(self.mapping, self.key, self.default)
            case _, _:
                setattr(self.mapping, self.key, value)

    def __delete__(self, _):
        delattr(self.mapping, self.key)

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        return f'{cls}({self.name}[{self.key!r}])'


class ModuleTargetAccessor(BaseMappingTargetAccessor[str, str, MutableMapping[str, V], T, V]):
    """
    A reference to a variable in a module.
    """
    @property
    def mapping(self) -> MutableMapping[str, V]:
        if self.descriptor not in sys.modules:
            raise NameError(f'Module {self.descriptor} not found')
        return sys.modules[self.descriptor].__dict__

    def __repr__ (self)-> str:
        cls = type(self).__name__.strip('_')
        return f'{cls}(sys.modules[{self.key!r}])'


class ContextLocalAccessor(ObjectTargetAccessor[ContextLocal, ContextLocal, ContextLocal, V]):
    """
    A reference to the target object for a proxy object, with the target living in a context variable.
    """
    def __get__(self, proxy: 'XGitProxy[ContextLocal, V]', objtype) -> ContextLocal:
        try:
            return getattr(self.descriptor, self.key)
        except NameError:
            ctx = ContextLocal()
            ctx = cast(ContextLocal, ctx)
            self.__set__(proxy, ctx)
            return ctx


class ContextMapAccessor(MappingTargetAccessor[K, V, ContextMap]):
    """
    A reference to the target object for a proxy object, with the target living in a context variable.
    """
    def __get__(self, proxy: 'XGitProxy[ContextMap, V]', objtype) -> ContextMap:
        try:
            return cast(ContextMap, self.descriptor[self.key])
            return cast(ContextMap, getattr(self.descriptor, self.key))
        except KeyError:
            ctx = ContextMap()
            ctx = cast(ContextMap, ctx)
            self.__set__(proxy, ctx)
            return ctx


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
        return f'{cls}(.{self.name}.{self.attribute})'


class XGitProxy(Generic[T,V]):
    """
    A proxy for items managed in other contexts.
    """
    def __getitem__(self, name):
        with ProxyMetadata.lock:
            return meta(self).adaptor.getitem(name)

    def __setitem__(self, name, value):
        with ProxyMetadata.lock:
            meta(self).adaptor.setitem(name, value)

    def __delitem__(self, name):
        with ProxyMetadata.lock:
            meta(self).adaptor.delitem(name)

    def __setattr__(self, name: str, value):
        with ProxyMetadata.lock:
            if name in ProxyMetadata._no_pass_through:
                return super().__setattr__(name, value)
            meta(self).adaptor.setattr(name, value)

    def __getattr__(self, name):
        with ProxyMetadata.lock:
            if name in ProxyMetadata._no_pass_through:
                try:
                    return super().__getattribute__(name)
                except AttributeError as ex:
                    print(ex)
                    pass
            return meta(self).adaptor.getattr(name)

    def __contains__(self, name):
        with ProxyMetadata.lock:
            return meta(self).adaptor.contains(name)

    def __hasattr__(self, name):
        with ProxyMetadata.lock:
            return meta(self).adaptor.hasattr(name)

    def __bool__(self):
        with ProxyMetadata.lock:
            return meta(self).adaptor.bool()

    def __repr__(self):
        try:
            name = meta(self).accessor.name
        except Exception:
            name = "<unbound>"
        try:
            t = target(self)
        except Exception:
            t = "<unbound>"
        return str(f'{type(self).__name__}({name=!r}, target={t})')


ProxyDeinitializer: TypeAlias = Callable[[], None]
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
    def __call__(self, descriptor: D, /, **kwargs) -> TargetAccessor[D,M, T, V]: ...


class AdapterFactory(Generic[D, M, T, V], Protocol):
    """
    A function that adapts a `TargetDescriptor` by wrapping it in an
    `ObjectAdaptor`. This can be a class (such as `AttributeAdapter` or `MappingAdapter`)
    or a factory function that returns an `ObjectAdaptor`.
    """
    def __call__(self, descriptor: TargetAccessor[D,M, T, V], /, **kwargs) -> ObjectAdaptor[T, V]: ...


@overload
def proxy(name: str,
          namespace: Any,
          accessor_factory: TargetAccessorFactory[D, M, T, V]=IdentityTargetAccessor,
          adaptor_factory: AdapterFactory[D, M, T, V]=ObjectAdaptor, /, *,
          type: type[V],
          instance_type: type[XGitProxy[T, V]] = XGitProxy[T, V],
          initializer: Optional[ProxyInitializer] = None,
          **kwargs
    ) -> V: ...

@overload
def proxy(name: str,
          namespace: Any,
          accessor_factory: TargetAccessorFactory[D, M, T, V]=IdentityTargetAccessor,
          adaptor_factory: AdapterFactory[D, M, T, V]=ObjectAdaptor, /, *,
          type: None=None,
          instance_type: type[XGitProxy[T, V]] = XGitProxy[T, V],
          initializer: Optional[ProxyInitializer] = None,
          **kwargs
    ) -> XGitProxy[T,V]: ...
def proxy(name: str,
          namespace: Any,
          accessor_factory: TargetAccessorFactory[D, M, T, V]=IdentityTargetAccessor,
          adaptor_factory: AdapterFactory[D, M, T, V]=ObjectAdaptor, /, *,
          type: Optional[type[V]] = None,
          instance_type: type[XGitProxy[T, V]] = XGitProxy[T, V],
          initializer: Optional[ProxyInitializer] = None,
          **kwargs
    ) -> XGitProxy[T,V]|V:
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
    accessor = accessor_factory(namespace, **kwargs)
    accessor.__set_name__(proxy, name)
    adaptor = adaptor_factory(accessor, **kwargs)
    ProxyMetadata._metadata[proxy] = ProxyMetadata(namespace, accessor, adaptor)

    if initializer is not None:
        ProxyMetadata.set_initializer(proxy, initializer)
    return proxy


class ProxyMetadata(Generic[T, V]):
    """
    Metadata for proxy objects.
    """
    lock: RLock = RLock()
    _metadata: WeakKeyDictionary[XGitProxy, 'ProxyMetadata'] = WeakKeyDictionary()
    __initializers: WeakKeyDictionary[XGitProxy, ProxyInitializer] = WeakKeyDictionary()
    __deinitializers: deque[ProxyDeinitializer] = deque()
    _no_pass_through: set[str] = {
            '_target', '__class__', '__dict__', '__dir__', '__doc__',
            '__module__', '__weakref__', '__orig_class__', '__orig_bases__',
        }

    __namespace: object
    @property
    def namespace(self) -> Any:
        return self.__namespace

    __accessor: TargetAccessor[object, object, T, V]
    @property
    def accessor(self) -> TargetAccessor[object, object, T, V]:
        return self.__accessor # type: ignore

    __adaptor: ObjectAdaptor[T, V]
    @property
    def adaptor(self) -> ObjectAdaptor[T, V]:
        return self.__adaptor

    def __init__(self, namespace: Any, accessor: TargetAccessor[D, M, T, V], adaptor: ObjectAdaptor[T, V], /):
        self.__namespace = namespace
        self.__accessor = accessor # type: ignore
        self.__adaptor = adaptor

    @staticmethod
    def set_initializer(proxy: 'XGitProxy[T, V]', initializer: ProxyInitializer):
        """
        Add an initializer to the proxy object.
        """
        ProxyMetadata.__initializers[proxy] = initializer

    @staticmethod
    def load():
        """
        Load the proxy metadata.
        """
        while len(ProxyMetadata.__initializers) > 0:
            with ProxyMetadata.lock:
                proxy, initializer = ProxyMetadata.__initializers.popitem()
                try:
                    deinitializer = initializer(proxy)
                except Exception as ex:
                    print(f'Error initializing proxy {proxy}: {ex}')
                if deinitializer is not None:
                    def deinit(proxy, deinitializer) -> 'ProxyDeinitializer':
                        def deinit():
                            with ProxyMetadata.lock:
                                try:
                                    deinitializer()
                                except Exception as ex:
                                    print(f'Error cleaning up proxy {proxy}: {ex}')
                        return deinit
                    ProxyMetadata.__deinitializers.append(deinit(proxy, deinitializer))

    @staticmethod
    def unload():
        """
        Unload the proxy metadata.
        """
        while len(ProxyMetadata.__deinitializers) > 0:
            with ProxyMetadata.lock:
                deinitializer = ProxyMetadata.__deinitializers.pop()
                try:
                    deinitializer()
                except Exception as ex:
                    print(f'Error cleaning up proxy: {ex}')


def meta(proxy: XGitProxy[T,V]) -> ProxyMetadata[T, V]:
    """
    Get the metadata for a proxy object.
    """
    meta = ProxyMetadata._metadata[proxy]
    if meta is None:
        raise AttributeError(f'No metadata for {proxy}')
    return meta


@overload
def target(proxy: 'T|XGitProxy[T, V]', /) -> T: ...
@overload
def target(proxy: 'T|XGitProxy[T, V]', value: T, /) -> None: ...
@overload
def target(proxy: 'T|XGitProxy[T, V]', /, *, delete: bool) -> None: ...
def target(proxy: 'T|XGitProxy[T, V]', value: _NoValue|T=_NO_VALUE, /, *, delete: bool=False) -> T|None:
    """
    Get, set, or delete the target object for a proxy object.

    With one argument, get the target object.

    With two arguments, set the target object to the value provided.

    With one positional argument and the `delete` keyword argument,
    delete the target object.

    Note: This affects the target object, not the proxy object, nor any
    container in which the target object is stored.

    For example, if the target object is stored in a dictionary or a module,
    the target object is the value in the dictionary or the module attribute.
    It does not affect what dictionary or module the proxy starts with to access
    with.

    If you need to switch the container in which the target object is stored,
    use another proxy object with `IdentityTargetAccessor`.
    
    `target` may be called with one argument on non-proxy objects, in which case
    it returns the object unchanged. This allows `target` to be used in a
    type-safe manner in code that may be passed either a proxy object or a
    non-proxy object.

    PARAMETERS:
    * `proxy`: The proxy object.
    * `value`: The value to set the target object to.
    * `delete`: If `True`, delete the target object.
    """
    
    match isinstance(proxy, XGitProxy), value, delete:
        case False, _NoValue(), _:
            return cast(T, proxy)
        case False, _, True:
            raise ValueError(f'Cannot delete target for {proxy}, which is not a proxy object')
        case False, _, _:
            raise ValueError(f'Cannot set target for {proxy}, which is not a proxy object')
        case True, _, _:
            proxy = cast(XGitProxy[T, V], proxy)

    with ProxyMetadata.lock:
        d: TargetAccessor[D, M, T, V]  = meta(proxy).accessor # type: ignore
        assert d is not None, f'No target descriptor for {proxy}'

        match value, delete:
            case _NoValue(), True:
                del d.target
            case _NoValue(), _:
                return d.target
            case _, _:
                d.target = value
        return None
