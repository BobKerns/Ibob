'''
A `View` provides an alternative way to look at the objects in a repository.

It acts as a proxy, so for most purposes you can interact with it as if you
were interacting with the objects themselves.

For example, a view of a list of tuples can be displayed as a table,
filtered, or sorted. The view itself is not a list, but it can be used
as one in most cases. You can iterate over it, index it, append to it,
and so on.

The view is a `Generic` class, so you can specify the type of the objects
and their intermediate representation. For example, a view of a list of
`Path` objects could be converted to a list of tuples of names, sizes, and
dates.

The default conversion is the identity function, so the target is also
the intermediate representation. You can change this by supplying a
conversion function that maps from `T` to `R`

You can supply display functions that maps from `R` to `str` to control
the behavior of the `str` and `repr` functions.

A separate display function can be supplied for the `pretty` function.
Rather than returning a string, this function should operate on its
own `RepresentationPrinter` object., after first checking for a cycle.

```
def my_pretty(myobj: R, p: RepresentationPrinter, cycle: bool):
    if cycle:
        p.text('...')
        return
    p.text(f'My object: {myobj}')
```

An alternative to using the proxy functionality is to wrap the objects
in a view before displaying them. This allows you to control the display
format without changing the objects themselves. This would only be
effective for the display loop, not for other operations. This can be
either an advantage or a disadvantage, depending on the use case.

The view is hashable, if the target object is, so it can be used as a
key in a dictionary or set, but this is probably neither useful nor
a good idea.

Views can have subviews, so a view of a list of list can apply a subview
to each of the sublists.

You can supply configurable objects for the filter, sort, and display
functions. This allows you to change the behavior of the view without
changing the view itself. This is useful for creating views that can
be used in different contexts.

The `View` class and its subclass provide a `config` method that returns
a configuration object that can be used to set the conversion, display,
and pretty functions. This allows you to create a view with a default
configuration that can be overridden by the user.

The methods and attributes to manipulate the all begin with an underscore.
This is to avoid conflicts with the target object. The target object is
stored in a private attribute, so you can access it with the `_target`
attribute. This is a property, so you can assign to it to change the
target object. This is useful for re-using the same view with different
objects.

The `_target_value` attribute returns the target object, converted to the
intermediate representation. This is useful for the display functions.

The `View` object may be called as a function, in which case it will
return the target object, converted to the intermediate representation.
The previous target object is saved and restored. (This is not thread-safe).
'''


from dataclasses import dataclass
from abc import abstractmethod
from typing import (
    Any, Callable,
    Optional, Protocol, TypeVar, Generic, cast,
)
from collections.abc import Iterable

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import _NO_VALUE, _NoValue


T = TypeVar('T')
'''
The type of the object in the view, for example `list[tuple[str, int, str]]
'''

Tcv = TypeVar('Tcv', covariant=True)
'''
The type of the object in the view, for example `list[tuple[str, int, str]]
'''
Txv = TypeVar('Txv', contravariant=True)
'''
The type of the object in the view, for example `list[tuple[str, int, str]]
'''

R = TypeVar('R')
Rcv = TypeVar('Rcv', covariant=True)
Rxv = TypeVar('Rxv', contravariant=True)
'''
The intermediate representation of the object, for example `list[tuple[str, int, str]]`

A conversion function from `T` to `R` should be supplied unless T == R

The display functions should handle R objects.
'''

K = TypeVar('K')
Kxv = TypeVar('Kxv', contravariant=True)
'''
The type of the keys in a mapping view.
'''
Kcv = TypeVar('Kcv', covariant=True)

X = TypeVar('X')
'''
The type of the extracted items in a `MultiView`.
'''
Xcv = TypeVar('Xcv', covariant=True)
Xxv = TypeVar('Xxv', contravariant=True)

class ConverterFn(Generic[Txv,Rcv], Protocol):
    '''
    A conversion function from `T` to `R`.
    '''
    @abstractmethod
    def __call__(self, x: Txv) -> Rcv: ...

class DisplayFn(Generic[Rxv], Protocol):
    '''
    A display function from `R` to `str`.
    '''
    @abstractmethod
    def __call__(self, x: Rxv) -> str: ...

class PrettyFn(Generic[Rxv], Protocol):
    '''
    A pretty function from `R` to `str`.
    '''
    @abstractmethod
    def __call__(self, x: Rxv, p: RepresentationPrinter, cycle: bool) -> None: ...


@dataclass
class ViewConfig(Generic[Txv, Rcv]):
    converter: Optional[ConverterFn[Txv,Rcv]] = None
    str_method: Optional[DisplayFn[Rcv]] = None
    repr_method: Optional[DisplayFn[Rcv]] = None
    pretty_method: Optional[PrettyFn[Rcv]] = None

class View(Generic[T, Rcv]):
    '''
    A view of an object.

    TYPE PARAMETERS
    ----------
    T: Any
        The type of the object to view.
    R: Any
        The intermediate representation of the object.
        This is the type of the object that is displayed
        by the `str`, `repr`, and `pretty` functions.

    PARAMETERS
    ----------
    target: T
        The object to view.
    converter: Optional[Callable[[T], R]]
        A function that converts the object to the intermediate representation.
    str: Optional[Callable[[R], str]]
        A function that converts the intermediate representation to a string.
    repr: Optional[Callable[[R], str]]
        A function that converts the intermediate representation to a string.
    pretty: Optional[Callable[[R, RepresentationPrinter, bool], None]]
        A function that converts the intermediate representation to a pretty string.
    '''
    __hashed: bool = False
    __target: T|_NoValue = _NO_VALUE
    @property
    def _target(self) -> T:
        '''
        Access this to get the underlying object. Assign to this to change
        the underlying object, re-using the same view.
        '''
        if self.__target is _NO_VALUE:
            raise ValueError('No target value')
        return cast(T, self.__target)
    @_target.setter
    def _target(self, value: T) -> None:
        '''
        Set this to change the underlying object, re-using
        the same view.

        Should not be called if the view is being hashed.
        '''
        if self.__hashed:
            raise ValueError('Cannot change the target of a hashed view')
        self.__target = value

    __converter: Optional[ConverterFn[T, Rcv]] = None
    @property
    def _converter(self) -> ConverterFn[T, Rcv]:
        '''
        The conversion function from the target object to the intermediate
        representation. If not supplied, the identity function is used.

        This function should be used to convert the target object to the
        intermediate representation.

        If the target object is already in the intermediate representation,
        this function should be the omitted.
        '''
        if self.__converter is None:
            return lambda x: cast(Rcv, x)
        return self.__converter
    @_converter.setter
    def _converter(self, value: Optional[ConverterFn[T, Rcv]]) -> None:
        self.__converter = value

    __str_method: Optional[DisplayFn[Rcv]] = None
    @property
    def _str(self) -> DisplayFn[Rcv]:
        '''
        The function that converts the intermediate representation to a string.
        If not supplied, the `str` function is used.
        '''
        if self.__str_method is None:
            return cast(DisplayFn[Rcv], str)
        return self.__str_method
    @_str.setter
    def _str(self, value: Optional[DisplayFn[Rcv]]) -> None:
        self.__str_method = value

    __repr_method: Optional[DisplayFn[Rcv]] = None
    @property
    def _repr(self) -> Callable[[Rcv], str]:
        '''
        The function that converts the intermediate representation to a string.
        If not supplied, the `repr` function is used.
        '''
        if self.__repr_method is None:
            return repr
        return self.__repr_method
    @_repr.setter
    def _repr_setter(self, value: Optional[DisplayFn[Rcv]]) -> None:
        self.__repr_method = value

    __pretty_method: Optional[PrettyFn[Rcv]] = None
    @property
    def _pretty(self) ->PrettyFn[Rcv]:
        '''
        The function that converts the intermediate representation to a pretty
        string. If not supplied, the equivalent of the `str` function is used.
        '''
        if self.__pretty_method is None:
            return cast(PrettyFn[Rcv], lambda x, p, c: p.text(str(x)))
        return self.__pretty_method
    @_pretty.setter
    def _pretty(self, value: Optional[PrettyFn[Rcv]]) -> None:
        self.__pretty_method = value


    def __init__(self,
                target: T|_NoValue = _NO_VALUE, *,
                config: Optional[ViewConfig[T, Rcv]] = None,
                converter: Optional[ConverterFn[T, Rcv]] = None,
                str_method: Optional[DisplayFn[Rcv]] = None,
                repr_method: Optional[DisplayFn[Rcv]] = None,
                pretty_method: Optional[PrettyFn[Rcv]] = None):
        if config:
            converter = config.converter or converter
            str_method = config.str_method or str_method
            repr_method = config.repr_method or repr_method
            pretty_method = config.pretty_method or pretty_method
        self.__hashed = False
        self.__target = cast(T, target)
        self.__converter = converter
        self.__str_method = str_method
        self.__repr_method = repr_method
        self.__pretty_method = pretty_method

    @staticmethod
    def config(converter: Optional[ConverterFn[T, Rcv]] = None,
                str_method: Optional[DisplayFn[Rcv]] = None,
                repr_method: Optional[DisplayFn[Rcv]] = None,
                pretty_method: Optional[PrettyFn[Rcv]] = None) -> ViewConfig[T, Rcv]:
        '''
        Create a configuration object for a view.
        This can be supplied as `config=` when creating a view to
        default the conversion function and other settings.
        '''
        return ViewConfig(converter=converter,
                          str_method=str_method,
                          repr_method=repr_method,
                          pretty_method=pretty_method)

    def __getattr__(self, name: str) -> Any:
        t = type(self)
        if hasattr(t, name):
            p = getattr(t, name, None)
            if p is not None and hasattr(p, '__get__'):
                return p.__get__(self)
        if (
            name.startswith('_')
            and not name.endswith('_')
            and '__' not in name
        ):
            # This is a private attribute of the view
            # That we got here means the attribute was not found.
            raise AttributeError(f'Attribute {name} not found on view {t.__name__}')
        return getattr(self._target, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self.__class__, name):
            super().__setattr__(name, value)
            return
        if (
            name.startswith('_')
            and not name.endswith('__')
            and '__' in name
        ):
            # This is a private attribute of the view
            return super().__setattr__(name, value)
        setattr(self._target, name, value)

    def __getitem__(self, key: Any) -> Any:
        return self._target[key]   # type: ignore

    def __setitem__(self, key: Any, value: Any) -> None:
        self._target[key] = value  # type: ignore

    def __iter__(self) -> Iterable:
        raise ValueError('Cannot iterate over a view')
        return iter(self._target)  # type: ignore

    def __len__(self) -> int:
        return len(self._target)   # type: ignore

    def __bool__(self) -> bool: # type: ignore
        if self.__target is _NO_VALUE:
            return False
        return bool(self._target)

    def __repr__(self) -> str:
        if self.__target is _NO_VALUE:
            return str(self)
        try:
            target = self._target_value
        except ValueError as ex:
            return f'...{ex}...'
        if self.__repr_method is None:
            return repr(target)
        return self.__repr_method(target)

    def __str__(self) -> str:
        if self.__target is _NO_VALUE:
            return f'{self.__class__.__name__}()'
        try:
            target = self._target_value
        except ValueError as ex:
            return f'{self.__class__.__name__}({ex})'
        if self.__str_method is None:
            return str(self._target)
        return self.__str_method(target)

    def __eq__(self, other: Any) -> bool:
        if self.__target is _NO_VALUE:
            return False
        return self.__target == other

    def __ne__(self, other: Any) -> bool:
        if self.__target is _NO_VALUE:
            return True
        return self.__target != other

    def __hash__(self) -> int:
        self.__hashed = True
        return hash(self._target)

    def __contains__(self, item: Any) -> bool:
        return item in self._target

    def __add__(self, other: Any) -> Any:
        return self._target + other

    def __radd__(self, other: Any) -> Any:
        return other + self._target

    def __iadd__(self, other: Any) -> Any:
        self._target += other
        return self

    def __mul__(self, other: int) -> Any:
        return self._target * other    # type: ignore

    def __rmul__(self, other: int) -> Any:
        return other * self._target    # type: ignore

    def __imul__(self, other: int) -> Any:
        self._target *= other      # type: ignore
        return self

    def __sub__(self, other: Any) -> Any:
        return self._target - other

    def __rsub__(self, other: Any) -> Any:
        return other - self._target

    def __isub__(self, other: Any) -> Any:
        self._target -= other
        return self

    def __truediv__(self, other: Any) -> Any:
        return self._target / other

    def __rtruediv__(self, other: Any) -> Any:
        return other / self._target

    def __itruediv__(self, other: Any) -> Any:
        self._target /= other
        return self

    def __floordiv__(self, other: Any) -> Any:
        return self._target // other

    def __rfloordiv__(self, other: Any) -> Any:
        return other // self._target

    def __ifloordiv__(self, other: Any) -> Any:
        self._target //= other
        return self

    def __mod__(self, other: Any) -> Any:
        return self._target % other

    def __rmod__(self, other: Any) -> Any:
        return other % self._target

    def __imod__(self, other: Any) -> Any:
        self._target %= other
        return self

    def __pow__(self, other: Any) -> Any:
        return self._target ** other

    def __rpow__(self, other: Any) -> Any:
        return other ** self._target

    def __ipow__(self, other: Any) -> Any:
        self._target **= other
        return self

    def __lshift__(self, other: Any) -> Any:
        return self._target << other

    def __rlshift__(self, other: Any) -> Any:
        return other << self._target

    def __ilshift__(self, other: Any) -> Any:
        self._target <<= other
        return self

    def __rshift__(self, other: Any) -> Any:
        return self._target >> other

    def __rrshift__(self, other: Any) -> Any:
        return other >> self._target

    def __irshift__(self, other: Any) -> Any:
        self._target >>= other
        return self

    def __and__(self, other: Any) -> Any:
        return self._target & other

    def __rand__(self, other: Any) -> Any:
        return other & self._target


    def __iand__(self, other: Any) -> Any:
        self._target &= other
        return self

    def __xor__(self, other: Any) -> Any:
        return self._target ^ other

    def __rxor__(self, other: Any) -> Any:
        return other ^ self._target

    def __ixor__(self, other: Any) -> Any:
        self._target ^= other
        return self

    def __or__(self, other: Any) -> Any:
        return self._target | other

    def __ror__(self, other: Any) -> Any:
        return other | self._target

    def __ior__(self, other: Any) -> Any:
        self._target |= other
        return self

    def __neg__(self) -> Any:
        return -self._target   # type: ignore

    def __pos__(self) -> Any:
        return +self._target   # type: ignore

    def __abs__(self) -> Any:
        return abs(self._target)   # type: ignore

    def __invert__(self) -> Any:
        return ~self._target   # type: ignore

    def __complex__(self) -> Any:
        return complex(self._target)   # type: ignore

    def __int__(self) -> Any:
        return int(self._target)   # type: ignore

    def __float__(self) -> Any:
        return float(self._target)  # type: ignore

    def __round__(self, ndigits: Optional[int] = None) -> Any:
        return round(self._target, ndigits)   # type: ignore

    def __trunc__(self) -> Any:
        return self._target.__trunc__()    # type: ignore

    def __floor__(self) -> Any:
        return self._target.__floor__()    # type: ignore

    def __ceil__(self) -> Any:
        return self._target.__ceil__()   # type: ignore

    def __enter__(self) -> Any:
        if self.__target is _NO_VALUE:
            return False
        return self._target.__enter__()    # type: ignore

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        if self.__target is _NO_VALUE:
            return False
        return self._target.__exit__(exc_type, exc_value, traceback)   # type: ignore

    def __delitem__(self, key: Any) -> None:
        del self._target[key]  # type: ignore

    @property
    def _target_value(self) -> Rcv:
        '''
        Return the target value, converted to the intermediate representation.
        If the second value is True,
        '''
        target = self._target
        if self.__converter:
            target = self.__converter(target)
        target = cast(Rcv, target)   # type: ignore
        return target

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool) -> None:
        '''
        A hook for the `pretty` function. This is called by the `pretty`
        function, which is called by the `display` function.
        '''
        if cycle:
            p.text('...')
            return
        try:
            if self.__pretty_method is None:
                p.text(str(self._target_value))
            else:
                target = self._target_value
                self.__pretty_method(target, p, cycle)
        except ValueError as e:
            p.text(f'...{e}...')

    def __call__(self, value: T):
        '''
        Convert the target object to the intermediate representation.
        '''
        old = self.__target
        try:
            self._target = value
            return self._target_value
        finally:
            self.__target = old
