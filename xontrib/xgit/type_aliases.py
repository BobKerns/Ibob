'''
Type aliases for xgit. These use the `type` statement to define the type
aliases. See type_aliases_310.py for the same type aliases defined using
`TypeAlias` from `typing`.
'''

from pathlib import Path, PurePosixPath
from typing import Callable, Literal, TypeVar

from xontrib.xgit.ids import ObjectId, GitRepositoryId

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

type GitReferenceType = Literal['ref', 'commit', 'tag', 'tree']
'''
The type of a git reference, that is, how an object is referenced.
'''

type GitObjectReference = tuple[
    GitRepositoryId,
    ObjectId|PurePosixPath,
    GitReferenceType,
]
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

# Invoker

type KeywordArity = Literal['+', '*', 0, 1, True, False]
'''
The number of arguments a keyword takes.

- `True`: Zero argument boolean flag, `True` if supplied
- `False`: Zero argument boolean flag, `False` if supplied
- `0`: Zero argument keyword, the flag name if supplied
- `1`: One argument follows the keyword.
- `+`: One or more arguments follow the keyword.
- `*`: Zero or more arguments follow the keyword.
'''

type KeywordSpec = tuple[KeywordArity, str]
'''
A keyword specification for a command.

PARAMETERS
----------
    - nargs: The number of arguments the keyword takes,
      or the boolean value for an un-negated (`--no-`)
      0-argument keyword.
    - key: The keyword supplied to the function.

USAGE
-----
See: `KeywordSpecs` for more information.
'''

type KeywordSpecs = dict[str, KeywordSpec]
'''
A dictionary of keyword specifications for a command.

PARAMETERS
----------
    - key: The keyword supplied to the function.
    - value: The keyword specification.

>>> `{'g': (1, 'gobbler')}`: -g <value> => `{'gobbler': 'value'}`

>>> `{'g': (0, 'gobbler')}`: -g => `['--gobbler']`

>>> `{'g': (True, 'gobbler')}`: -g => `{'gobbler': True}`

>>> `{'flag': (True, 'flag')}`: --flag => `{'flag': True}`

>>> `{'flag': (1, 'flag')}`: --flag value => `{'flag': 'value'}`

>>> `{'flag': ('+', 'flag')}`: --flag value1 value2 => `{'flag': ['value1', 'value2']}`

>>> `{'flag': ('*', 'flag'})`: --flag value1 value2 value3 => `{
    'flag': ['value1', 'value2']
    }`

>>> `{'flag': (0, 'flag')}`: --no-flag => `['--no-flag']`

The default behavior is to treat `--foo` if specified by
`{'foo': (True, 'foo')}` and `--no-foo` as if specified by
`{'no-foo': (False, 'foo')}`.

In addition, hyphens are mapped to underscore, so that
`--foo-bar` is treated as `{'foo-bar': (True, 'foo_bar')}`.
'''

type KeywordInputSpec = str|KeywordArity|KeywordSpec
'''
Input for a keyword specification. If only a `KeywordArity` is supplied,
the keyword is assumed to be the same as the flag name. Otherwise, if
a string is supplied, the keyword is assumed to be the string and the
`KeywordArity` is assumed to be `True`.
'''

type KeywordInputSpecs = dict[str, KeywordInputSpec]
'''
Input to specify keyword specifications for a command. This is converted
to `KeywordSpecs` for use in the invoker.
'''
# Tables

type HeadingStrategy = Literal['none', 'name', 'heading', 'heading-or-name']

type ColumnKeys = list[str|int]

def list_of[E](e: E) -> type[list[E]]:
    return list[*e]


type DirectoryKind = Literal['repository', 'worktree', 'directory']
