'''
Compatibility aliases for Python 3.10 type hints, before the
type statement was added in 3.12.

We try to make these invisible to type checkers; they're for
downrev runtime compatibility only.
'''
from typing import Literal, TYPE_CHECKING, Any, Callable, Literal, TypeVar, Generic
from pathlib import Path, PurePosixPath

from pytest import Directory

if not TYPE_CHECKING:

    GitHash = str
    ContextKey = tuple[Path, PurePosixPath, GitHash, GitHash]
    GitLoader = Callable[[], None]
    GitEntryMode = Literal[
        "040000",  # directory
        "100755",  # executable
        "100644",  # normal file
        "160000",  # submodule
        "20000",  # symlink
    ]
    GitObjectType = Literal["blob", "tree", "commit", "tag"]
    GitEntryKey = tuple[Path, PrePosixPath|None, str, str|None]
    GitObjectReference = tuple[ContextKey, str | None]
    CleanupAction = Callable[[], None]

    AdaptorMethod = Literal[
        'getitem', 'setitem', 'delitem', 'setattr', 'getattr', 'contains', 'hasattr', 'bool'
    ]
    ProxyAction = Literal['get', 'set', 'delete', 'bool']
    ProxyDeinitializer = Callable[[], None]

    JsonAtomic = None|str|int|float|bool
    JsonArray = list['JsonData']
    JsonObject = dict[str,'JsonData']
    JsonData = JsonAtomic|JsonArray|JsonObject


    _Suffix = TypeVar('_Suffix', bound=str)

    class _FileMarker(Generic[_Suffix]):
        "Marker to distinguish File from Path"
        @classmethod
        def suffix(cls) -> _Suffix:
            ...
    Directory = Path|str
    File = Path | _FileMarker
    PythonFile = Path | _FileMarker[Literal['.py']]
else:
    GitHash = Any
    ContextKey = Any
    GitLoader = Any
    GitEntryMode = Any
    GitObjectType = Any
    GitEntryKey = Any
    GitObjectReference = Any
    CleanupAction = Any
    AdaptorMethod = Any
    ProxyAction = Any
    ProxyDeinitializer = Any
    JsonAtomic = Any
    JsonArray = Any
    JsonObject = Any
    JsonData = Any
    Directory = Any
    File = Any
    PythonFile = Any