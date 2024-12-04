'''
Compatibility aliases for Python 3.10 type hints, before the
type statement was added in 3.12.

We try to make these invisible to type checkers; they're for
downrev runtime compatibility only.
'''
from typing import Literal, Any, Callable
from pathlib import Path, PurePosixPath

from xontrib.xgit.ids import ObjectId, GitRepositoryId

def t_type_of(e):
    return list

GitLoader = Callable[[], None]
GitEntryMode = Literal[
    "040000",  # directory
    "100755",  # executable
    "100644",  # normal file
    "160000",  # submodule
    "20000",  # symlink
]
GitObjectType = Literal["blob", "tree", "commit", "tag"]
GitReferenceType = Literal['ref', 'commit', 'tag', 'tree']
GitObjectReference = tuple[GitRepositoryId, ObjectId|PurePosixPath, GitReferenceType]
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

DirectoryKind = Literal['repository', 'worktree', 'directory']
