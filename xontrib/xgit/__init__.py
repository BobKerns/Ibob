"""
Functions and commands for working with Git repositories interactively in `xonsh`.

An [xonsh](https://xon.sh) command-line environment for exploring git repositories
and histories. With `xgit`, you seamlessly blend displayed information and pythonic
data manipulation, in the powerful python-native [xonsh](https://xon.sh) shell.

This provides a set of commands that return objects for both display
and pythonic manipulation.

See https://xonsh.org/ for more information about `xonsh`.
"""

from xontrib.xgit.types import (
    GitEntryMode,
    GitObjectType,
    ObjectId,
)
from xontrib.xgit.object_types import (
    GitId, GitObject,
    GitBlob,
    GitTree,
    GitCommit,
    GitTagObject,
)
from xontrib.xgit.entry_types import (
    GitEntry,
    GitEntryTree,
    GitEntryBlob,
    GitEntryCommit,
    EntryObject,
    ParentObject,
)
from xontrib.xgit.ref_types import (
    GitRef,
    Branch,
    Tag,
    RemoteBranch
)
from xontrib.xgit.context_types import (
    GitRepository,
    GitWorktree,
    GitContext,
)
from xontrib.xgit.main import (
    _load_xontrib_,
    _unload_xontrib_,
)
from xontrib.xgit.xgit_cd import git_cd
from xontrib.xgit.xgit_pwd import git_pwd
from xontrib.xgit.xgit_ls import git_ls

__all__ = (
    "_load_xontrib_",
    "_unload_xontrib_",
    'git_cd',
    'git_pwd',
    'git_ls',
    "ObjectId",
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
    "GitEntry",
    "GitEntryTree",
    "GitEntryBlob",
    "GitEntryCommit",
    "EntryObject",
    "ParentObject",
    "GitRef",
    "Branch",
    "Tag",
    "RemoteBranch",
)
