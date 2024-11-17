'''
Auxiliary types for xgit xontrib. These are primarily used for internal purposes.

Types for public use will be defined in the xgit module via `__init__.py`. and the
`__all__` variable.
'''

from typing import (
    Generic, Protocol, TypeVar,
)
from pathlib import Path

try:
    from xontrib.xgit.type_aliases import (
        CleanupAction,
        ContextKey,
        GitLoader,
        GitEntryMode,
        GitObjectType,
        GitEntryKey,
        GitObjectReference,
        AdaptorMethod,
        ProxyAction,
        ProxyDeinitializer,
        GitHash,
        JsonArray,
        JsonAtomic,
        JsonObject,
        JsonData,
        Directory,
        File,
        PythonFile,
    )
except SyntaxError:
    from xontrib.xgit.type_aliases_310 import (
        CleanupAction,
        ContextKey,
        GitLoader,
        GitEntryMode,
        GitObjectType,
        GitEntryKey,
        GitObjectReference,
        AdaptorMethod,
        ProxyAction,
        ProxyDeinitializer,
        GitHash,
        JsonArray,
        JsonAtomic,
        JsonObject,
        JsonData,
        Directory,
        File,
        PythonFile,
    )

class _NoValue:
    """A type for a marker for a value that is not passed in."""
    __match_args__ = ()
    def __repr__(self):
        return '_NO_VALUE'


_NO_VALUE = _NoValue()
"""A marker value to indicate that a value was not supplied"""

S = TypeVar('S', contravariant=True)
V = TypeVar('V', covariant=True)


class InitFn(Generic[S, V], Protocol):
    """
    A function that initializes a value from a source.
    """
    def __call__(self, source: S, /) -> V: ...
