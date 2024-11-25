'''
Type aliases for xgit. These use the `type` statement to define the type
aliases. See type_aliases_310.py for the same type aliases defined using
`TypeAlias` from `typing`.
'''

from pathlib import Path, PurePosixPath
from typing import Callable, Literal, TypeVar

from xonsh.built_ins import XonshSession

type CleanupAction = Callable[[], None]
'''
An action to be taken when the xontrib is unloaded.
'''
type LoadAction = Callable[[XonshSession], None|CleanupAction]

type GitHash = str
'''
A git hash. Defined as a string to make the code more self-documenting.

Also allows using `GitHash` as a type hint that drives completion.
'''


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

type GitEntryKey = tuple[Path, PurePosixPath|None, str, str, str|None]

type GitRepositoryId = str
"""
A unique identifier for a git repository.
"""

type GitReferenceType = Literal['ref', 'commit', 'tag', 'tree']
'''
The type of a git reference, that is, how an object is referenced.
'''

type GitObjectReference = tuple[GitRepositoryId, GitHash|PurePosixPath, GitReferenceType]
"""
A reference to a git object in a tree in a repository.
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