"""
A module to create description of an object for debugging or tests.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generic, Iterable, Literal, Mapping, Optional, Protocol, Sequence, TypeAlias, TypeVar, TypedDict, cast

def is_sequence(obj):
    return isinstance(obj, Sequence)

def is_mapping(obj):
    return isinstance(obj, Mapping)

JsonAtomic: TypeAlias = None|str|int|float|bool
"JSON Atomic Datatypes"
JsonArray: TypeAlias = list['JsonData']
"JSON Array"
JsonObject: TypeAlias = dict[str,'JsonData']
"JSON Object"
JsonData: TypeAlias = JsonAtomic|JsonArray|JsonObject
"JSON Data"

JsonContainerType: TypeAlias = Literal['list', 'dict', 'object', 'type']

class JsonErrorMsg(TypedDict):
    _cls: str
    _msg: str

class JsonError(TypedDict):
    _error: list[JsonErrorMsg]

class JsonMaxDepth(TypedDict):
    _id: int
    _maxdepth: int

class JsonRef(TypedDict):
    _ref: int

class JsonContainer(TypedDict):
    _id: int

class JsonList(JsonContainer):
    _list: list['JsonReturn']

class JsonMapping(JsonContainer):
    _map: 'JsonKV'

class JsonInstance(JsonContainer):
    _cls: str
    _attrs: 'JsonKV'

class JsonType(JsonContainer):
    _class_name: str
    _attrs: 'JsonKV'

JsonKV: TypeAlias = 'dict[str, JsonReturn]'

JsonReturn: TypeAlias = JsonAtomic|JsonError|JsonList|JsonInstance|JsonMapping|JsonType|JsonRef|JsonMaxDepth


H = TypeVar('H', bound='JsonKV|JsonReturn', covariant=True)
class JsonHandler(Generic[H], Protocol):
    def __call__(self, x: Any, describer: 'JsonDescriber', /) -> H:
        ...

@dataclass
class JsonDescriber:
    recursing: set[int] = field(default_factory=set)
    max_depth: int = 100
    special_types: dict[type,JsonHandler[JsonKV]] = field(default_factory=dict)
    include_private: bool = False
    _current_depth: int = -1
    """
    Recursion level.

    VALUES:
    - 0 or >0: The current recursion level.
    - -1: Not currently converting an object.
    - -2: Maximum recursion depth reached
        """
    @property
    @contextmanager
    def depth(self):
        old_depth = self._current_depth
        self._current_depth = old_depth + 1
        depth = self._current_depth
        if self._current_depth >= self.max_depth:
            depth = -2
        try:
            yield depth
        finally:
            self._current_depth = old_depth

    def _errchk(self, f: JsonHandler, *args, **kwargs) -> JsonReturn|JsonError:
        """
        Run a function and return the result or a `JsonError` structure if
        the function raises an exception.
        """
        try:
            return f(*args, **kwargs)
        except Exception as ex:
            exl: list[JsonErrorMsg] = []
            while ex is not None:
                exl.append({'_cls': type(ex).__name__, '_msg': str(ex)})
                ex = ex.__cause__
            return {'_error': exl}

    def _attr(self, x: object, attr: str) -> JsonReturn:
        """
        Get an attribute from an object and return its JSON representation,
        or a `JsonError` structure if the attribute does not exist or errors
        on access.
        """
        return self._errchk(lambda *_: self.to_json(getattr(x, attr)))

    def _item(self, x: Mapping[int|str, Any], key:str) -> JsonReturn:
        """
        Extract a key's value from a `Mapping` and return its JSON representation,
        or a `JsonError` structure if the key does not exist or errors
        on access.
        """
        return self._errchk(lambda *_: self.to_json(x[key]))

    def _valid_keys(self, x: object) -> Iterable[tuple[str, Any]]:
        """
        Get the valid attributes for an object.
        """
        return ((k, self._attr(x,k)) for k  in vars(x) if self.valid_key(k))

    def _instance(self, x: Any, handler: JsonHandler[JsonKV]) -> JsonReturn:
        """
        Get the JSON representation of an instance.
        """
        return {
            "_cls": type(x).__name__,
            "_id": id(x),
            '_attrs': handler(x, self)
        }

    def valid_key(self, k) -> bool:
        """
        Check if a key is valid for conversion to JSON.

        The default method rejects keys that start with an underscore,
        unless `include_private` is set to `True`.
        """
        return self.include_private or not k.startswith('_')

    def valid_value(self, x: Any) -> bool:
        """
        Check if a value is valid for conversion to JSON.
        """
        return not callable

    def _container_type(self, obj: Any) -> JsonContainerType:
        match obj:
            case obj if is_mapping(obj): return 'dict'
            case obj if is_sequence(obj): return 'list'
            case type(): return 'type'
            case int()|float()|str()|bool()|None:
                raise TypeError(f'Not a container: {obj}')
            case _: return 'object'

    def _max_depth(self, obj: Any) -> JsonMaxDepth:
        return {
            '_id': id(obj), # May not exist elsewhere!
            '_maxdepth': self._current_depth,
        }

    def _ref(self, obj: Any) -> JsonRef|None:
        if id(obj) not in self.recursing:
            return None
        match obj:
            case int()|float()|bool()|str()|None:
                return None
            case _:
                self.recursing.add(id(obj))
                return {
                    '_ref': id(obj),
                }


    def to_json(self, obj: Any) -> JsonReturn:
        """
        Perform the conversion to JSON.

        You probably don't want to call this directly, but use the `to_json` function instead.

        You probably don' want to override this method, but instead add a handler to the
        `special_types` dictionary, or override the `valid_key` or `valid_value` methods.

        PARAMETERS:
        - obj: Any
            The object to convert to JSON.
        """
        ref = self._ref(obj)
        if ref:
            return ref

        match obj:
            case str() | int() | float() | bool() | None:
                return obj
            case obj if is_sequence(obj):
                with self.depth as depth:
                    if depth < 0:
                        return self._max_depth(obj)
                    return {
                        '_id': id(obj),
                        '_list': [self.to_json(v) for v in obj]
                    }
            case obj if is_mapping(obj):
                with self.depth as depth:
                    if depth < 0:
                        return self._max_depth(obj)
                    items = {str(k):self.to_json(v) for k,v in obj.items()}
                    return {
                        '_id': id(obj),
                        '_map': items
                    }
            case a if type(a) in self.special_types:
                with self.depth as depth:
                    if depth <0:
                        return self._max_depth(obj)
                    handler: JsonHandler[JsonKV] = self.special_types[type(a)]
                    return self._instance(obj, handler)
            case type():
                with self.depth as depth:
                    if depth < 0:
                        return self._max_depth(obj)
                    attrs: JsonKV = {
                            k: self._attr(obj, k)
                            for k in dir(obj)
                            if self.valid_key(k)
                        }
                    return {
                        '_id': id(obj),
                        '_class_name': obj.__name__,
                        '_attrs': attrs
                    }
            case a:
                with self.depth as depth:
                    if depth < 0:
                        return self._max_depth(obj)
                    def default_handler(*_) -> dict[str,JsonReturn]:
                        return {
                            k: self._attr(a, k)
                            for k, v in self._valid_keys(a)
                            if self.valid_value(v)
                        }
                    return self._instance(a, default_handler)


def to_json(obj: Any,
            describer: Optional[JsonDescriber] = None,
            max_levels: int = 100,
            special_types: dict[type,JsonHandler] = {},
            include_private: bool = False,
        ) -> JsonReturn:
    """
    Create a JSON representation of an object.

    PARAMETERS:
    - obj: Any
        The object to describe.
    - describer: Optional[JsonDescriber]
        A describer object to use for the conversion. If not supplied,
        a new one is created with the following parameters.
    - max_levels: int = 100
        The maximum number of levels to recurse into the object.
    - special_types: dict[type,JsonHandler] = {}
        A mapping of types to functions that will handle the conversion of the
        object to JSON.
    - include_private: bool = False
        Whether to include private attributes in the output.
    """
    if describer is None:
        describer = JsonDescriber(
            max_depth=max_levels,
            special_types=special_types,
            include_private=include_private,
            )
    return describer.to_json(obj)


class RemapError(ValueError):
    ...

def remap_ids(obj: JsonReturn, argname: str) -> JsonReturn:
    "Canonicalize ID's for comparison"
    _cnt: int = 0
    _id_map: dict[int,int] = dict()
    def remap_id(id: int):
        nonlocal _cnt
        if id in _id_map:
            return _id_map[id]
        _new_id = _cnt
        _cnt += 1
        _id_map[id] = _new_id
        return _new_id
    def _remap_ids(obj: JsonReturn) -> JsonReturn:
        match obj:
            case None|int()|float()|bool()|str():
                return obj
            case {'_id': _id, '_map': kwargs}:
                return {
                    '_id': remap_id(_id),
                    '_map': {
                        k:_remap_ids(kwargs[k])
                        for k in sorted(kwargs.keys())
                    }
                }
            case {'_id': _id, '_list': lst}:
                return {
                    '_id': remap_id(_id),
                    '_list': [
                        _remap_ids(v)
                        for v in lst
                    ]
                }
            case {'_id': _id, '_cls': _cls, '_attrs': attrs}:
                return {
                    '_id': remap_id(_id),
                    '_cls': _cls,
                    '_attrs': {
                        k:_remap_ids(attrs[k])
                        for k,v in sorted(attrs.keys())
                    }
                }
            case {'_id': _id, '_type_class': _type_class, '_attrs': attrs}:
                return {
                    '_id': remap_id(_id),
                    '_type_class': _type_class,
                    '_attrs': {
                        k:_remap_ids(attrs[k])
                        for k in sorted(attrs.keys())
                    }
                }
            case {'_id': _id, '_maxdepth': _maxdepth}:
                return {
                    '_id': remap_id(_id),
                    '_maxdepth': _maxdepth,
                }
            case {'_ref': _ref}:
                return cast(JsonRef, {'_ref': remap_id(_ref)})
            case _:
                raise ValueError(f'Unrecognized JSON: {obj}')
    try:
        return _remap_ids(obj)
    except ValueError as ex:
        raise RemapError(f'Failed to parse {argname}: {obj}') from ex
