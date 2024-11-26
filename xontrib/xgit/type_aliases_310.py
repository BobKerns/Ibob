'''
Compatibility aliases for Python 3.10 type hints, before the
type statement was added in 3.12.

We try to make these invisible to type checkers; they're for
downrev runtime compatibility only.
'''
from typing import Literal, TYPE_CHECKING, Any, Callable, Literal, TypeVar, Generic
from pathlib import Path, PurePosixPath

from xonsh.built_ins import XonshSession

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
    GitEntryKey = tuple[Path, PurePosixPath|None, str, str|None]
    GitRepositoryId = str
    GitReferenceType = Literal['ref', 'commit', 'tag', 'tree']
    GitObjectReference = tuple[GitRepositoryId, GitHash|PurePosixPath, GitReferenceType]
    CleanupAction = Callable[[], None]
    LoadAction = Callable[[XonshSession], None|CleanupAction]
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

    KeywordArity = Literal['+', '*', 0, 1, True, False]
    KeywordSpec = tuple[KeywordArity, str]
    KeywordSpecs = dict[str, KeywordSpec]
    KeywordInputSpec = str|KeywordArity|KeywordSpec
    KeywordInputSpecs = dict[str, KeywordInputSpec]

    HeadingStrategy = Literal['none', 'name', 'heading', 'heading-or-name']
    ColumnKeys = list[str|int]|list[str]|list[int]
   
else:
    GitHash = str
    ContextKey =  tuple[Path, PurePosixPath, GitHash, GitHash]
    GitLoader = Callable[[], None]
    GitEntryMode = Literal[
        "040000",  # directory
        "100755",  # executable
        "100644",  # normal file
        "160000",  # submodule
        "20000",  # symlink
    ]
    GitObjectType = Literal["blob", "tree", "commit", "tag"]
    GitEntryKey = Any
    GitObjectReference = tuple
    GitRepositoryId = str
    GitReferenceType = str
    CleanupAction = Callable[[], None]
    LoadAction = Callable[[XonshSession], None|CleanupAction]
    JsonAtomic = Any
    JsonArray = list
    JsonObject = dict
    JsonData = Any

    Directory = Path|str
    File = Path
    PythonFile = Path

    KeywordArity = Literal['+', '*', 0, 1, True, False]
    KeywordSpec = tuple[KeywordArity, str]
    KeywordSpecs = dict[str, KeywordSpec]
    KeywordInputSpec = str|KeywordArity|KeywordSpec
    KeywordInputSpecs = dict[str, KeywordInputSpec]

    HeadingStrategy = Literal['none', 'name', 'heading', 'heading-or-name']
    ColumnKeys = list[str|int]|list[str]|list[int]
    
def type_of(e) -> type[list[Any]]:
    return list
