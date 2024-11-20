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
key in a dictionary or set.

Views can have subviews, so a view of a list of list can apply a subview
to each of the sublists.

You can supply configurable objects for the filter, sort, and display
functions. This allows you to change the behavior of the view without
changing the view itself. This is useful for creating views that can
be used in different contexts.
'''

from typing import (
    Any, Callable, Iterable, Iterator, Mapping,
    Optional, TypeVar, Generic, cast,
)

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import _NO_VALUE, _NoValue

T = TypeVar('T')
'''
The type of the object in the view, for example `list[tuple[str, int, str]]
'''
R = TypeVar('R')
'''
The intermediate representation of the object, for example `list[tuple[str, int, str]]`

A conversion function from `T` to `R` should be supplied unless T == R

The display functions should handle R objects.
'''

X = TypeVar('X')
'''
A generic type variable.
'''


class View(Generic[T, R]):
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
        if self.__target == _NO_VALUE:
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

    __converter: Optional[Callable[[T], R]] = None
    @property
    def _converter(self) -> Callable[[T], R]:
        '''
        The conversion function from the target object to the intermediate
        representation. If not supplied, the identity function is used.

        This function should be used to convert the target object to the
        intermediate representation.

        If the target object is already in the intermediate representation,
        this function should be the omitted.
        '''
        if self.__converter is None:
            return lambda x: cast(R, x)
        return self.__converter
    @_converter.setter
    def _converter(self, value: Optional[Callable[[T], R]]) -> None:
        self.__converter = value

    __str: Optional[Callable[[R], str]] = None
    @property
    def _str(self) -> Callable[[R], str]:
        '''
        The function that converts the intermediate representation to a string.
        If not supplied, the `str` function is used.
        '''
        if self.__str is None:
            return str
        return self.__str
    @_str.setter
    def _str(self, value: Optional[Callable[[R], str]]) -> None:
        self.__str = value

    __repr: Optional[Callable[[R], str]] = None
    @property
    def _repr(self) -> Callable[[R], str]:
        '''
        The function that converts the intermediate representation to a string.
        If not supplied, the `repr` function is used.
        '''
        if self.__repr is None:
            return repr
        return self.__repr
    @_repr.setter
    def _repr_setter(self, value: Optional[Callable[[R], str]]) -> None:
        self.__repr = value

    __pretty: Optional[Callable[[R, RepresentationPrinter, bool], None]] = None
    @property
    def _pretty(self) -> Callable[[R, RepresentationPrinter, bool], None]:
        '''
        The function that converts the intermediate representation to a pretty
        string. If not supplied, the equivalent of the `str` function is used.
        '''
        if self.__pretty is None:
            return cast(Callable[[R, RepresentationPrinter, bool], None], lambda x, p, c: p.text(str(x)))
        return self.__pretty
    @_pretty.setter
    def _pretty(self, value: Optional[Callable[[R, RepresentationPrinter, bool], None]]) -> None:
        self.__pretty = value


    def __init__(self,
                target: T|_NoValue = _NO_VALUE, *,
                converter: Optional[Callable[[T], R]] = None,
                str: Optional[Callable[[R], str]] = None,
                repr: Optional[Callable[[R], str]] = None,
                pretty: Optional[Callable[[R, RepresentationPrinter, bool], None]] = None):
        self.__hashed = False
        self.__target = cast(T, target)
        self.__converter = converter
        self.__str = str
        self.__repr = repr
        self.__pretty = pretty

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self.__class__, name):
            super().__setattr__(name, value)
            return
        setattr(self._target, name, value)

    def __getitem__(self, key: Any) -> Any:
        return self._target[key]   # type: ignore

    def __setitem__(self, key: Any, value: Any) -> None:
        self._target[key] = value  # type: ignore

    def __iter__(self) -> Iterable:
        return iter(self._target)  # type: ignore

    def __len__(self) -> int:
        return len(self._target)   # type: ignore

    def __bool__(self) -> bool: # type: ignore
        if self.__target == _NO_VALUE:
            return False
        return bool(self._target)

    def __repr__(self) -> str:
        if self.__target == _NO_VALUE:
            return str(self)
        try:
            target = self._target_value
        except ValueError as ex:
            return f'...{ex}...'
        if self.__repr is None:
            return repr(target)
        return self.__repr(target)

    def __str__(self) -> str:
        if self.__target == _NO_VALUE:
            return f'{self.__class__.__name__}()'
        try:
            target = self._target_value
        except ValueError as ex:
            return f'{self.__class__.__name__}({ex})'
        if self.__str is None:
            return str(self._target)
        return self.__str(target)

    def __eq__(self, other: Any) -> bool:
        if self.__target == _NO_VALUE:
            return False
        return self.__target == other

    def __ne__(self, other: Any) -> bool:
        if self.__target == _NO_VALUE:
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
        if self.__target == _NO_VALUE:
            return False
        return self._target.__enter__()    # type: ignore

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        if self.__target == _NO_VALUE:
            return False
        return self._target.__exit__(exc_type, exc_value, traceback)   # type: ignore

    def __delitem__(self, key: Any) -> None:
        del self._target[key]  # type: ignore

    @property
    def _target_value(self) -> R:
        '''
        Return the target value, converted to the intermediate representation.
        If the second value is True,
        '''
        target = self._target
        if self.__converter:
            target = self.__converter(target)
        target = cast(R, target)   # type: ignore
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
            if self.__pretty is None:
                p.text(str(self._target_value))
            else:
                target = self._target_value
                target = cast(R, target)
                self.__pretty(target, p, cycle)
        except ValueError as e:
            p.text(f'...{e}...')

class SequenceView(View[Iterable[T], Iterable[R]]):
    '''
    A view of a sequence.

    By default, the items are extracted using the `__iter__` method,
    so this view is only useful for objects that support this method.
    You may supply a custom _extractor function to overcome this.

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
    target: Iterable[T]
        The object to view.
    prefilter: Optional[Callable[[T], bool]]
        A function that filters the items before they are converted.
    postfilter: Optional[Callable[[R], bool]]
        A function that filters the items after they are converted.
    converter: Optional[Callable[[T], R]]
        A function that converts the item values to the intermediate
        representation.
    sort: Optional[Callable[[R], Any]]
        A function that sorts the items after they are converted
    '''
    def __init__(self, target: Iterable[T]|_NoValue = _NO_VALUE, *,
                extractor: Optional[Callable[[Iterable[T]], Iterable[T]]] = None,
                prefilter: Optional[Callable[[T], bool]] = None,
                postfilter: Optional[Callable[[R], bool]] = None,
                converter: Optional[Callable[[T], R]] = None,
                sort: Optional[Callable[[R], Any]] = None,
                 **kwargs):
        '''
        PARAMETERS
        ----------
        target: Iterable[T]
            The object to view.
        prefilter: Optional[Callable[[T], bool]]
            A function that filters the items before they are converted.
        postfilter: Optional[Callable[[R], bool]]
            A function that filters the items after they are converted.
        converter: Optional[Callable[[T], R]]
            A function that converts the item values to the intermediate
            representation.
        sort: Optional[Callable[[R], Any]]
            A function that sorts the items after they are converted.
        '''
        self.__extractor = extractor
        self.__prefilter = prefilter
        self.__postfilter = postfilter
        self.__sort = sort
        super().__init__(target, **kwargs)

    __converter: Optional[Callable[[T], R]] = None
    @property
    def _converter(self) -> Callable[[T], R]:
        '''
        The conversion function from the target object to the intermediate
        representation. If not supplied, the identity function is used.

        This function should be used to convert the target object to the
        intermediate representation.

        If the target object is already in the intermediate representation,
        this function should be the omitted.
        '''
        if self.__converter is None:
            return lambda x: cast(R, x)
        return self.__converter
    @_converter.setter
    def _converter(self, value: Optional[Callable[[T], R]]) -> None:
        self.__converter = value

    @property
    def _target_value(self) -> Iterator[R]:
        '''
        Return the target value, converted to the intermediate representation.
        '''
        target = self._target
        if target == _NO_VALUE:
            raise ValueError('No target value')
        if self.__extractor:
            target = self.__extractor(target)
        if self.__prefilter:
            target = (e for e in target if self.__prefilter(e))
        if self.__converter:
            target = (self.__converter(e) for e in target)
        target = cast(Iterable[R], target)
        if self.__postfilter:
            target = (e for e in target if self.__postfilter(e))
        if self.__sort:
            target = sorted(target, key=self.__sort)
        return iter(target)

    __extractor: Optional[Callable[[Iterable[T]], Iterable[T]]] = None
    @property
    def _extractor(self) -> Callable[[Iterable[T]], Iterable[T]]:
        if self.__extractor is None:
            return lambda x: x
        return self.__extractor
    @_extractor.setter
    def _extractor(self, value: Optional[Callable[[Iterable[T]], Iterable[T]]]) -> None:
        self.__extractor = value

    __prefilter: Optional[Callable[[T], bool]] = None
    @property
    def _prefilter(self) -> Optional[Callable[[T], bool]]:
        return self.__prefilter
    @_prefilter.setter
    def _prefilter(self, value: Optional[Callable[[T], bool]]) -> None:
        self.__prefilter = value

    __postfilter: Optional[Callable[[R], bool]] = None
    @property
    def _postfilter(self) -> Optional[Callable[[R], bool]]:
        return self.__postfilter
    @_postfilter.setter
    def _postfilter(self, value: Optional[Callable[[R], bool]]) -> None:
        self.__postfilter = value

    __sort: Optional[Callable[[R], Any]] = None
    @property
    def _sort(self) -> Optional[Callable[[R], Any]]:
        return self.__sort
    @_sort.setter
    def _sort(self, value: Optional[Callable[[R], Any]]) -> None:
        self.__sort = value


K = TypeVar('K')

class MappingView(View[Mapping[K,T], Iterator[tuple[K,R]]]):
    '''
    A view of a mapping.

    By default, the items are extracted using the `items` method,
    so this view is only useful for objects that support this method.
    You may supply a custom _extractor function to overcome this.

    PARAMETERS
    ----------
    target: Mapping[K,T]
        The object to view.
    prefilter: Optional[Callable[[K,T], bool]]
        A function that filters the items before they are converted.
    postfilter: Optional[Callable[[K,R], bool]]
        A function that filters the items after they are converted.
    extractor: Optional[Callable[[Mapping[K,T]], Iterable[tuple[K,T]]]]
        A function that extracts the items from the mapping.
        Defaults to using the `items` method.
    converter: Optional[Callable[[K,T], R]]
        A function that converts the item values to the intermediate
        representation.
    sort: Optional[Callable[[K,R], Any]]
        A function that sorts the items after they are converted
    '''
    def __init__(self, target: Mapping[K,T]|_NoValue = _NO_VALUE, *,
                prefilter: Optional[Callable[[K,T], bool]] = None,
                postfilter: Optional[Callable[[K,R], bool]] = None,
                converter: Optional[Callable[[K,T], R]] = None,
                extractor: Optional[Callable[[Mapping[K,T]], Iterable[tuple[K,T]]]] = None,
                sort: Optional[Callable[[K,R], Any]] = None,
                 **kwargs):
        super().__init__(target, **kwargs)
        self.__extractor = extractor
        self.__converter = converter
        self.__prefilter = prefilter
        self.__postfilter = postfilter
        self.__sort = sort

    @property
    def _target_value(self) -> Iterator[tuple[K,R]]:
        target = self._target
        if self._extractor:
            target = self._extractor(target)
        else:
            target = target.items()
        if self._prefilter:
            target = (e for e in target if self._prefilter(*e))
        if self._converter:
            target = (self._converter(*e) for e in target)
        target = cast(Iterator[tuple[K,R]], target)
        if self._postfilter:
            target = (e for e in target if self._postfilter(*e))
        if self._sort:
            def sort_wrapper(kv: tuple[K,R]) -> Any:
                k,v =kv
                assert self._sort is not None
                return self._sort(k,v)
            target = iter(sorted(target, key=sort_wrapper))
        return iter(target)

    __extractor: Optional[Callable[[Mapping[K,T]], Iterable[tuple[K,T]]]] = None
    @property
    def _extractor(self) -> Callable[[Mapping[K,T]], Iterable[tuple[K,T]]]:
        if self.__extractor is None:
            return lambda x: x.items()
        return self.__extractor
    @_extractor.setter
    def _extractor(self, value: Optional[Callable[[Mapping[K,T]], Iterable[tuple[K,T]]]]) -> None:
        self.__extractor = value


    __converter: Optional[Callable[[K,T], R]] = None
    @property
    def _converter(self) -> Callable[[K,T], R]:
        if self.__converter is None:
            return lambda k, x: cast(R, x)
        return self.__converter
    @_converter.setter
    def _converter(self, value: Optional[Callable[[K,T], R]]) -> None:
        self.__converter = value

    __prefilter: Optional[Callable[[K,T], bool]] = None
    @property
    def _prefilter(self) -> Optional[Callable[[K,T], bool]]:
        return self.__prefilter
    @_prefilter.setter
    def _prefilter(self, value: Optional[Callable[[K,T], bool]]) -> None:
        self.__prefilter = value

    __postfilter: Optional[Callable[[K,R], bool]] = None
    @property
    def _postfilter(self) -> Optional[Callable[[K,R], bool]]:
        return self.__postfilter
    @_postfilter.setter
    def _postfilter(self, value: Optional[Callable[[K,R], bool]]) -> None:
        self.__postfilter = value

    __sort: Optional[Callable[[K,R], Any]] = None
    @property
    def _sort(self) -> Optional[Callable[[K,R], Any]]:
        return self.__sort
    @_sort.setter
    def _sort(self, value: Optional[Callable[[K,R], Any]]) -> None:
        self.__sort = value

class AttributeView(View[T, Iterator[tuple[str,Any]]]):
    '''
    A view of the attributes of an object.

    By default, the attributes are extracted using the `dir` function,
    so this view is only useful for objects that have attributes. You
    may supply a custom _extractor function to overcome this.

    PARAMETERS
    ----------
    target: T
        The object to view.
    prefilter: Optional[Callable[[str,Any], bool]]
        A function that filters the attributes before they are converted.
    postfilter: Optional[Callable[[str,Any], bool]]
        A function that filters the attributes after they are converted.
    converter: Optional[Callable[[str,Any], Any]]
        A function that converts the attribute values to the intermediate
        representation.
    sort: Optional[Callable[[str,Any], Any]]
        A function that sorts the attributes after they are converted.
    '''
    def __init__(self, target: T|_NoValue = _NO_VALUE, *,
                prefilter: Optional[Callable[[str,Any], bool]] = None,
                postfilter: Optional[Callable[[str,Any], bool]] = None,
                converter: Optional[Callable[[str,Any], Any]] = None,
                sort: Optional[Callable[[str,Any], Any]] = None,
                 **kwargs):
        super().__init__(target, **kwargs)
        self.__prefilter = prefilter
        self.__postfilter = postfilter
        self.__converter = converter
        self.__sort = sort

    __extractor: Optional[Callable[[T], Iterable[str]]] = None
    @property
    def _extractor(self) -> Callable[[T], Iterable[str]]:
        if self.__extractor is None:
            return lambda x: dir(x)
        return self.__extractor
    @_extractor.setter
    def _extractor(self, value: Optional[Callable[[T], Iterable[str]]]) -> None:
        self.__extractor = value

    __converter: Optional[Callable[[str,Any], Any]] = None
    @property
    def _converter(self) -> Callable[[str,Any], Any]|None:
        if self.__converter is None:
            return lambda k, x: x
        return self.__converter
    @_converter.setter
    def _converter(self, value: Optional[Callable[[str,Any], Any]]) -> None:
        self.__converter = value

    __prefilter: Optional[Callable[[str,Any], bool]] = None
    @property
    def _prefilter(self) -> Optional[Callable[[str,Any], bool]]:
        return self.__prefilter
    @_prefilter.setter
    def _prefilter(self, value: Optional[Callable[[str,Any], bool]]) -> None:
        self.__prefilter = value

    __postfilter: Optional[Callable[[str,Any], bool]] = None
    @property
    def _postfilter(self) -> Optional[Callable[[str,Any], bool]]:
        return self.__postfilter
    @_postfilter.setter
    def _postfilter(self, value: Optional[Callable[[str,Any], bool]]) -> None:
        self.__postfilter = value

    __sort: Optional[Callable[[str,Any], Any]] = None
    @property
    def _sort(self) -> Optional[Callable[[str,Any], Any]]:
        return self.__sort
    @_sort.setter
    def _sort(self, value: Optional[Callable[[str,Any], Any]]) -> None:
        self.__sort = value