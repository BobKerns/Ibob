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
    GitRepository,
    GitWorktree,
    GitContext,
)
from xontrib.xgit.xgit_main import (
    _load_xontrib_,
    _unload_xontrib_,
    git_cd,
    git_pwd,
    git_ls,
)

__all__ = (
    "_load_xontrib_",
    "_unload_xontrib_",
    'git_cd',
    'git_pwd',
    'git_ls',
    "GitHash",
    "GitId",
    "GitObject",
    "GitBlob",
    "GitTree",
    'GitCommit',
    'GitTagObject',
    "GitRepository",
    "GitWorktree",
    "GitContext",
    "GitEntryMode",
    "GitObjectType",
    "GitTreeEntry",
    '__version__',
)
