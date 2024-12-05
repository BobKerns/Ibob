'''
A `MultiView` is a `View` that extracts multiple values from a target object.

These can be considered a sequence of rows, with each row containing
a key-value pair. There is always one key and one value. The key can be
anything—even a constant value, but it is typically a string or integer
index. The value is then the value of the target object at that key.

If no other value is obvious, use an `enumeration` of the rows to provide
a row index.

Processing begins with target object. The processing proceeds as follows:

- The target object is supplied.
    - The target object can be supplied in any of these ways:
        - As a parameter to the constructor.
        - By assignment to the `_target` attribute.
        - By using the `MultiView` as a function, and supplying the target.
- The `extractor` function is called with the target object.
    - The `extractor` function returns an `Iterable` of key-value pairs.
    - If no `extractor` is supplied, `default_extractor` is used.
    - If no decomposition is possible, the type name is used as the key
        and the object is used as the value, in a single pair.
- For each pair, an optional `prefilter` is called with the key and value.
    - If the `prefilter` returns `False`, the pair is skipped.
- The key and value are passed to the `converter` function.
    - The `converter` function converts the key and value to an
        intermediate key and object, the selected view of the row.
    - If no `converter` is supplied, the key and value are used directly,
        and become the intermediate form.
- The intermediate key and object are passed to the `postfilter` function.
    - If the `postfilter` returns `False`, the row is skipped.
    - If no `postfilter` is supplied, the row is not skipped.
- The intermediate key and object are passed to the optional `sort` function.
    - The `sort` function returns a key that is used to sort the rows.
    - Unlike sort key functions passed directly to `sorted`, the `sort`
        function is passed two arguments, the intermediate key and object.
- The sorted rows are available as the `_target_value` attribute.
- The `str`, `repr`, and `pretty` functions use the `_target_value`
    to display the object.
'''

from abc import abstractmethod
from collections.abc import Mapping, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from datetime import datetime, date, timedelta, timezone
from itertools import count
from typing import (
    Any, Callable, Generic, Optional, cast,
    Protocol,
)

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import _NO_VALUE, _NoValue
from xontrib.xgit.views.view import (
    View, T, Txv, K, Kcv, Kxv, X, Xcv, Xxv, Rxv, Rcv
)

class ConverterFnMulti(Generic[Kxv, Txv, Rcv], Protocol):
    '''
    A conversion function from `K`, `T` to `R`.
    '''
    @abstractmethod
    def __call__(self, k: Kxv, x: Txv) -> Rcv: ...

class DisplayFnMulti(Generic[Kxv, Rxv], Protocol):
    '''
    A display function from `K`, `R` to `str`.
    '''
    @abstractmethod
    def __call__(self, k: Kxv, x: Rxv) -> str: ...

class PrettyFnMulti(Generic[Kxv, Rxv], Protocol):
    '''
    A pretty function from `K`, `R` to `str`.
    '''
    @abstractmethod
    def __call__(self, k: Kxv, x: Rxv,
                 p: RepresentationPrinter, cycle: bool) -> None: ...

class ExtractorFnMulti(Generic[Txv, Kcv, Xcv], Protocol):
    '''
    An extractor function from `T` to `Iterable[tuple[K, X]]`.
    '''
    @abstractmethod
    def __call__(self, x: Txv) -> Iterable[tuple[Kcv, Xcv]]: ...

class FilterFnMulti(Generic[Kxv, Xxv], Protocol):
    '''
    A filter function from `K`, `X` to `bool`.
    '''
    @abstractmethod
    def __call__(self, k: Kxv, x: Xxv) -> bool: ...


class SortFnMulti(Generic[Kxv, Xxv], Protocol):
    '''
    A sort key function from `K`, `X` to `Any.
    '''
    @abstractmethod
    def __call__(self, k: Kxv, x: Xxv) -> Any: ...


ATOMIC = tuple({
    str, bytes, bytearray, int, float, complex, bool, Exception,
    Decimal , Fraction, datetime, date, timedelta, timezone,
    memoryview, type(None), type(Ellipsis), type(NotImplemented), type(...),
    })
'''
The types that are considered atomic, and do not need to be converted.
'''

def default_extractor(x: T) -> Iterable[tuple[int|str, T]]:
    '''
    The default extractor for a `MultiView`. This assumes that the target
    object can be converted to an iterable of tuples, where the first element
    is the key.
    '''
    if isinstance(x, ATOMIC):
        return [(type(x).__name__, x)]
    if isinstance(x, (dict, Mapping)):
        with suppress(Exception):
            return x.items()
    if hasattr(x, 'keys') and hasattr(x, 'values'):
        with suppress(Exception):
            return zip(x.keys(), x.values()) # type: ignore
    if hasattr(x, 'items') and callable(x.items): # type: ignore
        with suppress(Exception):
            c = count()
            return (v if isinstance(v, Sequence) and len(v) == 2 else (next(c), v)
                    for v in x.items()) # type: ignore
    if hasattr(x, 'values') and callable(x.values): # type: ignore
        with suppress(Exception):
            c = count()
            return ((next(c), v) for v in x.values()) # type: ignore
    if isinstance(x, (Iterable, Sequence)):
        with suppress(Exception):
            return enumerate(x)
    if hasattr(x, '__iter__') or hasattr(x, '__getitem__'):
        with suppress(Exception):
            return enumerate(iter(cast(Iterable, x)))
    with suppress(Exception):
        def shorten(k: str, v: Any) -> str:
            if k.startswith('_'):
                s = k.split('__', maxsplit=1)
                return s[-1].strip('_')
            return k.rstrip('_')
        return {shorten(k,v):v for k,v in vars(x).items()}.items()
    with suppress(Exception):
        return enumerate(iter(cast(Iterable[T], x)))
    return [(0, x)]

@dataclass
class MultiViewConfig(Generic[Txv, Kxv, Xxv, Rcv]):
    '''
    Configuration for a `MultiView`.
    '''
    extractor: Optional[ExtractorFnMulti[Txv,Kxv,Xxv]] = None
    prefilter: Optional[FilterFnMulti[Kxv, Xxv]] = None
    converter: Optional[ConverterFnMulti[Kxv, Xxv, Rcv]] = None
    postfilter: Optional[FilterFnMulti[Kxv, Rcv]] = None
    sort: Optional[SortFnMulti[Kxv, Rcv]] = None
    str_method: Optional[DisplayFnMulti[Kxv, Rcv]] = None
    repr_method: Optional[DisplayFnMulti[Kxv, Rcv]] = None
    pretty_method: Optional[PrettyFnMulti[Kxv, Rcv]] = None


class MultiView(Generic[T, K, X, Rcv], View[T, Iterable[tuple[K, Rcv]]]):
    '''
    A view of multiple objects.

    This is a view of a sequence of sub-objects, such as a list of lists or a
    list of dictionaries. The objects are converted to the intermediate
    representation, and the result is returned as an iterable of the
    intermediate representations.

    The objects are extracted using an extractor method, so this view is
    only useful for objects that support this method. You may supply a
    custom _extractor function to overcome this.

    TYPE PARAMETERS
    ----------
    T: Any
        The type of the object to view.
    K: Any
        The type of the keys in the intermediate representation.
    R: Any
        The intermediate representation of the object.
        This is the type of the object that is displayed
        by the `str`, `repr`, and `pretty` functions.

    PARAMETERS
    ----------
    target: Iterable[T]
        The object to view.
    extractor: Optional[Callable[[T], Iterable[tuple[K, X]]]]
    prefilter: Optional[Callable[[K, X], bool]]
        A function that filters the items before they are converted.
    converter: Optional[Callable[[K, X], R]]
        A function that converts the item values to the intermediate
        representation.
    postfilter: Optional[Callable[[K, R], bool]]
        A function that filters the items after they are converted.
    sort: Optional[Callable[[K, R], Any]]
        A function that sorts the items after they are converted
    str_method: Optional[DisplayFnMulti[K, R]]
        A function that converts the intermediate representation to a string.
    repr_method: Optional[DisplayFnMulti[K, R]]
        A function that converts the intermediate representation to a string.
    pretty_method: Optional[PrettyFnMulti[K, R]]
        A function that converts the intermediate representation to a string.
    config: Optional[MultiViewConfig[T, K, X, Rcv]]
        A configuration object that can be used to set the parameters.
    '''
    def __init__(self, target: T|_NoValue = _NO_VALUE, *,
                config: Optional[MultiViewConfig[T, K, X, Rcv]] = None,
                extractor: Optional[ExtractorFnMulti[T,K,X]] = None,
                prefilter: Optional[FilterFnMulti[K,X]] = None,
                converter: Optional[ConverterFnMulti[K,X,Rcv]] = None,
                postfilter: Optional[FilterFnMulti[K, Rcv]] = None,
                sort: Optional[SortFnMulti[K, Rcv]] = None,
                str_method: Optional[DisplayFnMulti[K, Rcv]] = None,
                repr_method: Optional[DisplayFnMulti[K, Rcv]] = None,
                pretty_method: Optional[PrettyFnMulti[K, Rcv]] = None,
                 **kwargs):
        '''
        PARAMETERS
        ----------
        target: Iterable[T]
            The object to view.
        config: Optional[MultiViewConfig[T, K, X, Rcv]]
            A configuration object that can be used to set the parameters.
        extractor: Optional[Callable[[T], Iterable[tuple[K, X]]]]
        prefilter: Optional[Callable[[K, X], bool]]
            A function that filters the items before they are converted.
        converter: Optional[Callable[[K, X], R]]
            A function that converts the item values to the intermediate
            representation.
        postfilter: Optional[Callable[[K, R], bool]]
            A function that filters the items after they are converted.
        sort: Optional[Callable[[R], Any]]
            A function that sorts the items after they are converted.
        str_method: Optional[DisplayFnMulti[K, R]]
        repr_method: Optional[DisplayFnMulti[K, R]]
        pretty_method: Optional[PrettyFnMulti[K, R]]
        '''
        if config is not None:
            extractor = extractor or config.extractor
            prefilter = prefilter or config.prefilter
            converter = converter or config.converter
            postfilter = postfilter or config.postfilter
            sort = sort or config.sort
            str_method = str_method or config.str_method
            repr_method = repr_method or config.repr_method
            pretty_method = pretty_method or config.pretty_method

        if str_method is not None:
            def _str_method(t: tuple[K, Rcv]) -> str:
                return str_method(*t)
            kwargs['str_method'] = _str_method

        if repr_method is not None:
            def _repr_method(t: tuple[K, Rcv]) -> str:
                return repr_method(*t)
            kwargs['repr_method'] = _repr_method

        if pretty_method is not None:
            def _pretty_method(t: tuple[K, Rcv],
                               p: RepresentationPrinter,
                               cycle: bool) -> None:
                return pretty_method(*t, p, cycle)
            kwargs['pretty_method'] = _pretty_method

        self.__extractor = extractor
        self.__multi_converter = converter
        self.__prefilter = prefilter
        self.__postfilter = postfilter
        self.__sort = sort

        super().__init__(target, **kwargs)

    __extractor: Optional[Callable[[T], Iterable[tuple[K, X]]]] = None
    @property
    def _extractor(self) -> Callable[[T], Iterable[tuple[K, X]]]:
        if self.__extractor is None:
            return cast(Callable[[T], Iterable[tuple[K,X]]], default_extractor)
        return self.__extractor
    @_extractor.setter
    def _extractor(self, value: Optional[Callable[[T], Iterable[tuple[K, X]]]]) -> None:
        self.__extractor = value


    __multi_converter: Optional[ConverterFnMulti[K, X, Rcv]] = None
    @property
    def _multi_converter(self) -> ConverterFnMulti[K, X, Rcv]:
        '''
        The conversion function from the target object to the intermediate
        representation. If not supplied, the identity function is used.

        This function should be used to convert the target object to the
        intermediate representation.

        If the target object is already in the intermediate representation,
        this function should be the omitted.
        '''
        converter = self.__multi_converter
        if converter is None:
            def _converter(k: K, x: X) -> tuple[K, Rcv]:
                return cast(tuple[K, Rcv], (k, x))
            converter = cast(ConverterFnMulti[K, X, Rcv], _converter)
            self.__multi_converter = converter
        return converter
    @_multi_converter.setter
    def _multi_converter(self, value: Optional[ConverterFnMulti[K, X, Rcv]]) -> None:
        self.__multi_converter = value

    @property
    def _target_value(self) -> Iterable[tuple[K, Rcv]]:
        '''
        Return the target value, converted to the intermediate representation.
        '''
        t_target: T = cast(T, self._target)
        if t_target is _NO_VALUE:
            raise ValueError('No target value')
        if self._extractor:
            x_target = self._extractor(t_target)
        else:
            x_target: Iterable[tuple[K, X]] = cast(Iterable[tuple[K, X]], t_target)

        if self.__prefilter:
            x_target = (e for e in x_target if self.__prefilter(*e))
        if self.__multi_converter:
            target = ((k, self.__multi_converter(k,v)) for k,v in x_target)
        else:
            target = cast(Iterable[tuple[K, Rcv]], x_target)

        if self.__postfilter:
            target = (e for e in target if self.__postfilter(*e))
        sort = self.__sort
        if sort is not None:
            def _sort(t: tuple[K, Rcv]) -> Any:
                k, x = t
                return sort(k, x)
            target = sorted(target, key=_sort)
        return target

    __prefilter: Optional[Callable[[K, X], bool]] = None
    @property
    def _prefilter(self) -> Optional[Callable[[K, X], bool]]:
        return self.__prefilter
    @_prefilter.setter
    def _prefilter(self, value: Optional[Callable[[K, X], bool]]) -> None:
        self.__prefilter = value

    __postfilter: Optional[Callable[[K, Rcv], bool]] = None
    @property
    def _postfilter(self) -> Optional[Callable[[K, Rcv], bool]]:
        return self.__postfilter
    @_postfilter.setter
    def _postfilter(self, value: Optional[Callable[[K, Rcv], bool]]) -> None:
        self.__postfilter = value

    __sort: Optional[Callable[[K, Rcv], Any]] = None
    @property
    def _sort(self) -> Optional[Callable[[K, Rcv], Any]]:
        return self.__sort
    @_sort.setter
    def _sort(self, value: Optional[Callable[[K, Rcv], Any]]) -> None:
        self.__sort = value
