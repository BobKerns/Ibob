'''
Type aliases for xgit. These use the `type` statement to define the type
aliases. See type_aliases_310.py for the same type aliases defined using
`TypeAlias` from `typing`.
'''

from pathlib import Path
from typing import Callable, Literal, TypeVar

type CleanupAction = Callable[[], None]
'''
An action to be taken when the xontrib is unloaded.
'''

type GitHash = str
'''
A git hash. Defined as a string to make the code more self-documenting.

Also allows using `GitHash` as a type hint that drives completion.
'''

type ContextKey = tuple[Path, Path, str|None, GitHash]
"""
A key for uniquely identifying a `GitContext`
"""


type GitLoader = Callable[[], None]
"""
A function that loads the contents of a git object.
Use InitFn for loading a single attribute. This is for the case
where the entire object is loaded.
"""


type GitEntryMode = Literal[
    "040000",  # directory
    "100755",  # executable
    "100644",  # normal file
    "160000",  # submodule
    "20000",  # symlink
]
"""
The valid modes for a git tree entry.
"""

type GitObjectType = Literal["blob", "tree", "commit", "tag"]
"""
Valid types for a git object.
"""

type GitEntryKey = tuple[Path, Path|None, str, str, str|None]

type GitObjectReference = tuple[Path, str | None]
"""
A reference to a git object in a tree in a repository.
"""

# Proxy

type AdaptorMethod = Literal[
    'getitem', 'setitem', 'delitem', 'setattr', 'getattr', 'contains', 'hasattr', 'bool'
]

type ProxyAction = Literal['get', 'set', 'delete', 'bool']
"""
Flags indicating the action being undertaken at the time of proxy access.
"""

type ProxyDeinitializer = Callable[[], None]
"""
A function returned from a `ProxyInitializer` that cleans up resources associated with the proxy object
on plugin unload.

"""

# Json

type JsonAtomic = None|str|int|float|bool
"JSON Atomic Datatypes"

type JsonArray = list['JsonData']
"JSON Array"

type JsonObject = dict[str,'JsonData']
"JSON Object"

type JsonData = JsonAtomic|JsonArray|JsonObject
"JSON Data"

# Decorators

_Suffix = TypeVar('_Suffix', bound=str)

type  Directory = Path|str
'''
A directory path.
'''
type File[_Suffix] = Path
type PythonFile = File[Literal['.py']]