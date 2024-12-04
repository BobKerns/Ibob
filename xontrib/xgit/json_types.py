'''
Types related to JSON serialization and deserialization.
'''
from typing import (
    TypeAlias, TypeVar, Optional, TypedDict, Protocol, Generic, Any,
TYPE_CHECKING,
)

from xontrib.xgit.types import JsonData, JsonAtomic

if TYPE_CHECKING:
    import xontrib.xgit.context_types as ct

class JsonRepresentation(TypedDict):
    '''
    A JSON representation of an object, other than the atomic JSON types.

    These are all distinguishable by the presence of specific sets of keys.
    '''
    pass

class ErrorMessageJson(JsonRepresentation):
    '''
    A single error message, with a class name and message.
    Part of a `JsonError` structure, not standalone
    '''
    _cls: str
    _msg: str


class ErrorJson(JsonRepresentation):
    '''
    A captured `Exception`, containing a list of error messages (nested causes)
    '''
    _error: list[ErrorMessageJson]


class CircularRefJson(JsonRepresentation):
    '''
    A circular reference to another object that has already been described.
    '''
    _ref: int


class ContainerJson(JsonRepresentation):
    '''
    Any value which contains other values.
    '''
    _id: int


class SequenceJson(ContainerJson):
    '''
    A JSON List, from any Python `Sequence` (except strings)
    '''
    _list: list['JsonReturn']


class MappingJson(ContainerJson):
    '''
    A JSON Object, from any Python `Mapping`.
    '''
    _map: 'JsonKV'


class InstanceJson(ContainerJson):
    '''
    A python instance, with a class name and attributes.
    '''
    _cls: str
    _attrs: 'JsonKV'


class TypeJson(ContainerJson):
    '''
    An explicit reference to a Python `type` object.
    '''
    _class_name: str
    _attrs: 'JsonKV'


class JsonJson(ContainerJson):
    '''
    An instance self-describing via JSON via a `to_json` method.
    '''
    _json: JsonData

class MaxDepthJson(ContainerJson):
    '''
    A marker indicating that the maximum recursion depth has been reached.
    '''
    _maxdepth: int


JsonReturn: TypeAlias = JsonAtomic|ErrorJson|SequenceJson|InstanceJson\
    |MappingJson|TypeJson|CircularRefJson|JsonJson|MaxDepthJson
'''
Any valid return type from the `to_json` function.
'''

JsonKV: TypeAlias = dict[str, JsonReturn] # type: ignore # mypy bug
'''
Key-Value pairs for JSON objects, such as maps or instances.
'''

H = TypeVar('H', bound='JsonKV|JsonReturn', covariant=True)
class JsonHandler(Generic[H], Protocol):
    def __call__(self, x: Any, describer: 'JsonDescriber', /) -> H: ...

class ToJsonOverride(Protocol):
    def __call__(self, x: Any, describer: 'JsonDescriber', /) -> JsonData:  ...

class FromJsonOverride(Protocol):
    def __call__(self, x: JsonData, describer: 'JsonDescriber', /) -> Any: ...


class JsonDescriber(Protocol):
    objects_by_id: dict[int,Any]
    overrides_by_id: dict[int,JsonData]
    references: dict[int, CircularRefJson]
    "Allows sharing of references within and between objects."
    max_depth: int = 100
    special_types: dict[type,'JsonHandler[JsonKV]']
    from_override_types: dict[type,FromJsonOverride]
    to_override_types: dict[type,ToJsonOverride]
    class_map: dict[str,type]
    class_names: dict[type,str]
    include_private: bool
    repository: 'ct.GitRepository' # (a refractory circular reference)
    context: 'ct.GitContext' # (a refractory circular reference)
    def to_json(self, obj: Any, cls: Optional[type|str]=None) -> JsonReturn:
        """
        Perform the conversion to JSON.

        You probably don't want to call this directly, but use the `to_json`
        function instead.

        You probably don' want to override this method, but instead add a handler to the
        `special_types` dictionary, or override the `valid_key` or `valid_value`
        methods.

        PARAMETERS:
        - obj: Any
            The object to convert to JSON.
        """
    def from_json(self, obj: Any,
                    cls: Optional[type|str] = None, /, *,
              repository: 'ct.GitRepository', # a refractory circular reference
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


class Jsonable(Protocol):
    """
    A protocol for objects that can be converted to JSON.
    """
    def to_json(self, describer: 'JsonDescriber') -> JsonData: ...
