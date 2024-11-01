"""
Functions and commands for working with Git repositories interactively in `xonsh`.

An [xonsh](https://xon.sh) command-line environment for exploring git repositories
and histories. With `xgit`, you seamlessly blend displayed information and pythonic
data manipulation, in the powerful python-native [xonsh](https://xon.sh) shell.

This provides a set of commands that return objects for both display
and pythonic manipulation.

See https://xonsh.org/ for more information about `xonsh`.
"""


from xontrib.xgit.xgit_types import (
    GitEntryMode,
    GitObjectType,
    GitHash,
    GitId,
    GitObject,
    GitBlob,
    GitTree,
    GitCommit,
    GitTagObject,
)
from xontrib.xgit.xgit_context import (
    _GitRepository,
    _GitWorktree,
    _GitContext,
)
from xontrib.xgit.xgit_main import (
    _load_xontrib_,
    _unload_xontrib_,
)

__all__ = (
    "_load_xontrib_",
    "_unload_xontrib_",
    "GitHash",
    "_GitId",
    "_GitObject",
    "_GitBlob",
    "_GitTree",
    "_GitRepository",
    "_GitWorktree",
    "_GitContext",
    "GitEntryMode",
    "GitObjectType",
    "GitTreeEntry",
)
