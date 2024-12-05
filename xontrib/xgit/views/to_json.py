"""
A module to create description of an object for debugging or tests.
"""
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import (
    Any, Optional, cast
)
from collections.abc import Iterable, Mapping, Sequence
from types import GenericAlias

from xontrib.xgit.context_types import GitRepository
from xontrib.xgit.views.json_types import (
   JsonData,
   SequenceJson, MappingJson, InstanceJson, TypeJson, MaxDepthJson,
   JsonJson, CircularRefJson, ErrorJson, ErrorMessageJson,
   JsonHandler, JsonReturn, FromJsonOverride, ToJsonOverride,
   JsonKV, JsonDescriber
)

def is_sequence(obj):
    return isinstance(obj, Sequence)

def is_mapping(obj):
    return isinstance(obj, Mapping)

def json_type(obj: Any, references: Optional[dict[int,Any]] = None) -> type:
    """
    Get the JSON representation type for an object.

    PARAMETERS:
    - obj: Any
        The object to get the JSON representation type for.
    - references: Optional[dict[int,Any]] = None
        A dictionary of references to objects that have already been described.
        If supplied, this will be used to resolve circular references.
        Otherwise. `CircularRefJson` will be returned for circular references.
    """
    match obj:
        case None|str()|int()|float()|bool():
            return type(obj)
        case {'_id': int(), '_list': list()}:
            return SequenceJson
        case {'_id': int(), '_map': dict()}:
            return MappingJson
        case {'_id': int(), '_cls': str(), '_attrs': dict()}:
            return InstanceJson
        case {'_id': int(), '_class_name': str(), '_attrs': dict()}:
            return TypeJson
        case {'_id': int(), '_maxdepth': int()}:
            return MaxDepthJson
        case {'_id': int(), '_json': Any()}:
            return JsonJson
        case {'_ref': int()}:
            if references is None or obj['_ref'] not in references:
                return CircularRefJson
            return json_type(references[obj['_ref']])
        case _:
            raise ValueError(f'Unrecognized JSON: {obj}')

@dataclass
class _JsonDescriber(JsonDescriber):
    repository: GitRepository
    objects_by_id: dict[int,Any] = field(default_factory=dict)
    overrides_by_id: dict[int,JsonData] = field(default_factory=dict)
    references: dict[int, CircularRefJson] = field(default_factory=dict)
    "Allows sharing of references within and between objects."
    max_depth: int = 100
    special_types: dict[type,JsonHandler[JsonKV]] = field(default_factory=dict)
    from_override_types: dict[type,FromJsonOverride] = field(default_factory=dict)
    to_override_types: dict[type,ToJsonOverride] = field(default_factory=dict)
    class_map: dict[str,type] = field(default_factory=dict)
    class_names: dict[type,str] = field(default_factory=dict)
    include_private: bool = False
    _current_depth: int = -1
    """
    Recursion level.

    VALUES:
    - 0 or >0: The current recursion level.
    - -1: Not currently converting an object.
    - -2: Maximum recursion depth reached
        """

    def __post_init__(self):
        for name, cls in self.class_map.items():
            self.class_names[cls] = name
        self.special_types.update({
            Path: lambda x, _: {'_path': str(x)},
            PurePosixPath: lambda x, _: {'_path': str(x)},
            })
        self.to_override_types.update({
            Path: lambda x, _: str(x),
            PurePosixPath: lambda x, _: str(x),
            })
        def json_to_path(json: JsonData, _: 'JsonDescriber') -> Path:
            return Path(str(json))
        self.from_override_types.update({
            Path: cast(FromJsonOverride, json_to_path),
            })
        self.context = self.repository.context

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

    def _errchk(self, f: JsonHandler, *args, **kwargs) -> JsonReturn|ErrorJson:
        """
        Run a function and return the result or a `JsonError` structure if
        the function raises an exception.
        """
        try:
            return f(*args, **kwargs)
        except Exception as ex:
            exl: list[ErrorMessageJson] = []
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
        keys = []
        with suppress(TypeError):
            keys = vars(x)
        return ((k, self._attr(x,k)) for k  in keys if self.valid_key(k))

    def _instance(self, x: Any, handler: JsonHandler[JsonKV]) -> JsonReturn:
        """
        Get the JSON representation of an instance.
        """
        return {
            "_cls": type(x).__name__,
            "_id": id(x),
            '_attrs': handler(x, self)
        }

    def class_to_name(self, cls: type) -> str:
        if cls in self.class_names:
            return self.class_names[cls]
        name = cls.__name__
        self.class_names[cls] = name
        self.class_map[name] = cls
        return name


    def name_to_class(self, name: str) -> type:
        if name in self.class_map:
            return self.class_map[name]
        cls = globals().get(name)
        if cls is not None:
            self.class_map[name] = cls
            self.class_names[cls] = name
            return cls
        raise ValueError(f'No class found for name: {name}')


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

    def _max_depth(self, obj: Any) -> MaxDepthJson:
        return {
            '_id': id(obj), # May not exist elsewhere!
            '_maxdepth': self._current_depth,
        }

    def _ref(self, obj: Any) -> CircularRefJson|None:
        _id = id(obj)
        match obj:
            case int()|float()|bool()|str()|None:
                return None
            case _ if _id not in self.objects_by_id:
                    return None
            case _:
                ref: CircularRefJson|None = self.references.get(_id)
                if ref is None:
                    ref = {
                        '_ref': id(obj),
                    }
                self.objects_by_id[_id] = obj
                self.references[_id] = ref
                return ref


    def _deref(self, obj: CircularRefJson|int) -> Any:
        if isinstance(obj, dict) and '_ref' in obj:
            obj = obj['_ref']

        if obj not in self.objects_by_id:
            raise ValueError(f'Unresolved circular reference: {obj}')
        return self.objects_by_id[obj]

    def find_class(self, _id: int, cls: str) -> type:
        cls_obj: type|GenericAlias
        if cls in self.class_map:
            cls_obj = self.class_map[cls]
        elif _id != 0 and _id in self.objects_by_id:
            cls_obj = cast(type|GenericAlias, self.objects_by_id[_id])
        elif cls in globals():
            cls_obj = globals()[cls]
            if (
                not isinstance(cls_obj, type)
                and not isinstance(cls_obj, GenericAlias)
            ):
                raise ValueError(f'Invalid class name: {cls}')
        else:
            raise ValueError(f'No class found for name: {cls}')
        if isinstance(cls_obj, GenericAlias):
            cls_obj = cls_obj.__origin__

        self.class_map[cls] = cls_obj
        self.class_names[cls_obj] = cls
        self.objects_by_id[_id] = cls_obj
        return cls_obj

    def instantiate_from_json(self, _id: int, cls: type|str, json: JsonData) -> Any:
        if _id in self.objects_by_id:
            return self.objects_by_id[_id]
        cls_obj = self.find_class(_id, cls) if isinstance(cls, str) else cls
        override = self.find_from_override(cls_obj)
        if override:
            return override(json, self)
        raise ValueError(f'No from_json method for {cls}')

    def instantiate(self, _id: int, cls: str, attrs: JsonKV) -> Any:
        if _id in self.objects_by_id:
            return self.objects_by_id[_id]
        cls_obj = self.find_class(0, cls)
        try:
            return cls_obj(**attrs)
        except Exception as ex:
            raise ValueError(f'{cls} is not re-instantiable.') from ex

    def find_to_override(self, cls: type) -> ToJsonOverride|None:
        return next(
            (
                v
                for v in (
                    self.to_override_types.get(t) or getattr(t, 'to_json', None)
                    for t in cls.__mro__
                )
                if v is not None
            ),
            None
        )

    def find_from_override(self, cls: type) -> ToJsonOverride|None:
        return next(
            (
                v
                for v in (
                    self.from_override_types.get(t) or getattr(t, 'from_json', None)
                    for t in cls.__mro__
                )
                if v is not None
            ),
            None
        )

    def to_json(self, obj: Any, cls: Optional[type|str]=None) -> JsonReturn:
        """
        Perform the conversion to JSON.

        You probably don't want to call this directly, but use the
        `to_json` function instead.

        You probably don' want to override this method, but instead
        add a handler to the `special_types` dictionary, or override
        the `valid_key` or `valid_value` methods.

        PARAMETERS:
        - obj: Any
            The object to convert to JSON.
        """
        ref = self._ref(obj)
        if ref:
            return ref
        _id = id(obj)
        if _id in self.overrides_by_id:
            return cast(JsonReturn, self.overrides_by_id[_id])
        override = self.find_to_override(type(obj))
        if override:
            val = override(obj, self)
            self.overrides_by_id[_id] = val
            return cast(JsonReturn, val)
        special_type = next(
            (
                t
                for t in type(obj).__mro__
                if t in self.special_types),
            None
        )
        match obj:
            case str() | int() | float() | bool() | None:
                return obj
            case _ if special_type and special_type in self.special_types:
                with self.depth as depth:
                    if depth <0:
                        return self._max_depth(obj)
                    handler: JsonHandler[JsonKV] = self.special_types[special_type]
                    return self._instance(obj, handler)
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
                if hasattr(a, 'to_json'):
                    return a.to_json(describer=self)
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


    def from_json(self, obj: Any, cls: Optional[type|str] = None, /, *,
                repository: GitRepository,
                describer: Optional['JsonDescriber'] = None,
                references: Optional[dict[int, Any]] = None,
                class_map: Optional[dict[str, type]] = None,
            )  -> Any:
        '''
        Get the python representation of a `JsonReturn` object.

        The return value may share structure with the input; do not
        modify the input after obtaining the python representation!

        PARAMETERS:
        - obj: Any
            The object to get the python representation for.
        - references: Optional[dict[int,Any]] = None
            A dictionary of references to objects that have already been described.
            If supplied, this will be used to record and resolve circular references.
        - class_map: Optional[dict,type] = None
            A mapping of class names to types, for use in instantiating instances.
        '''
        if class_map is None:
            class_map = dict()
        if references is None:
            references = dict()
        if cls is not None:
            return self.instantiate_from_json(0, cls, obj)
        match obj:
            case None|str()|int()|float()|bool():
                return obj
            case {'_id': int(_id), '_list': list(value)}:
                value = [
                    from_json(v,
                                repository=repository,
                                describer=describer)
                    for v in value
                ]
                references[_id] = value
                return value
            case {'_id': int(_id), '_map': dict(value)}:
                value = {
                    k: from_json(v,
                                 repository=repository,
                                 describer=describer,
                                 )
                    for k,v in value.items()
                }
                return value
            case {'_id': int(_id), '_cls': str(_cls), '_attrs': dict(attrs)}:
                attrs = {
                    k: from_json(v,
                                 repository=repository,
                                 describer=describer)
                    for k,v in attrs.items()
                }
                value = self.instantiate(_id, _cls, attrs)
                references[_id] = value
                return value
            case {'_id': int(_id), '_class_name': str(_cls), '_attrs': dict()}:
                type_value = self.find_class(_id, _cls)
                references[_id] = type_value
                if isinstance(type_value, GenericAlias):
                    return type_value.__origin__
                return type_value
            case {'_id': int(_id), '_maxdepth': int(depth)}:
                if _id in references:
                    return references[_id]
                raise ValueError(f'Maximum depth({depth}) reached for {_id}')
            case {'_id': int(_id), '_cls': str(_cls), '_json': json}:
                value = self.instantiate_from_json(_id, _cls, json)
                references[_id] = value
                return value
            case {'_ref': int(_id)}:
                if references is None or _id not in references:
                    raise ValueError(f'Unresolved circular reference: {obj}')
                return references[_id]
            case _:
                raise ValueError(f'Unrecognized JSON: {obj}')


def to_json(obj: Any, cls: Optional[type|str] = None, /, *,
            repository: GitRepository,
            describer: Optional[JsonDescriber] = None,
            max_levels: int = 100,
            special_types: Optional[dict[type, JsonHandler]] = None,
            override_types: Optional[dict[type, ToJsonOverride]] = None,
            include_private: bool = False,
            class_map: Optional[dict[str, type]] = None,
            objects_by_id: Optional[dict[int, Any]] = None,
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
        object to JSON by returning a dictionary of key-value pairs.
    - override_types: dict[type,JsonOverride] = {}
        A mapping of types to functions that will handle the conversion of the
        object to JSON by returning a JSON data structure.
    - include_private: bool = False
        Whether to include private attributes in the output.
    - class_map: dict[str,type]
        A mapping of class names to types, for use in instantiating instances.
        Names will typically be the unqualified class name, but may be any string.
    - objects_by_id: dict[int,Any]
        A dictionary of objects that have already been described, indexed by their ID.
    """
    if override_types is None:
        override_types = {}
    if objects_by_id is None:
        objects_by_id = dict()
    if class_map is None:
        class_map = dict()
    if special_types is None:
        special_types = {}
    if describer is None:
        describer = _JsonDescriber(
            repository=repository,
            max_depth=max_levels,
            special_types=special_types,
            to_override_types=override_types,
            include_private=include_private,
            class_map=class_map,
            objects_by_id=objects_by_id,
            )
    return describer.to_json(obj, cls)


def from_json(obj: JsonData, cls: Optional[type|str] = None, /, *,
              repository: GitRepository,
            describer: Optional['JsonDescriber'] = None,
            references: Optional[dict[int, Any]] = None,
            class_map: Optional[dict[str, type]] = None,
            )  -> Any:
    '''
    Get the python representation of a `JsonReturn` object.

    The return value may share structure with the input; do not
    modify the input after obtaining the python representation!

    PARAMETERS:
    - obj: Any
        The object to get the python representation for.
    - references: Optional[dict[int,Any]] = None
        A dictionary of references to objects that have already been described.
        If supplied, this will be used to record and resolve circular references.
    - class_map: Optional[dict,type] = None
        A mapping of class names to types, for use in instantiating instances.
    '''
    if class_map is None:
        class_map = dict()
    if references is None:
        references = dict()
    if describer is None:
        describer = _JsonDescriber(
            repository=repository,
            objects_by_id=references,
            class_map=class_map,
            )
    return describer.from_json(obj, cls,
                               repository=repository,
                               describer=describer,
                               references=references,
                               class_map=class_map)

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
                        for k in sorted(attrs.keys())
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
                return cast(CircularRefJson, {'_ref': remap_id(_ref)})
            case _:
                raise ValueError(f'Unrecognized JSON: {obj}')
    try:
        return _remap_ids(obj)
    except ValueError as ex:
        raise RemapError(f'Failed to parse {argname}: {obj}') from ex
