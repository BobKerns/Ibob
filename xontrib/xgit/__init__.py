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
    CommitId,
    TreeId,
    BlobId,
    TagId,
    GitError,
    GitValueError,
    RepositoryNotFoundError,
    WorktreeNotFoundError,
    GitException,
    GitNoWorktreeException,
    GitNoRepositoryException,
    DirectoryKind,    
)

from xontrib.xgit.utils import (
    path_and_parents,
    pre,
    post,
    prepost,
    print_if,
    relative_to_home,
    shorten_branch,
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
    Note,
    Replacement,
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
from xontrib.xgit.views import (
    View,
    ViewConfig,
    MultiView,
    TableView,
    Column,
    ColumnKeys,
    ColumnDict,
    HeadingStrategy,
    ExtractorFnMulti,
)
from xontrib.xgit.invoker import (
    Invoker,
    SharedSessionInvoker,
    EventInvoker,
    CommandInvoker,
    PrefixCommandInvoker,
)
from xontrib.xgit.runners import (
    Runner,
    SharedSessionRunner,
    EventRunner,
    Command,
    PrefixCommand,
)
from xontrib.xgit.decorators import (
    session,
    event_handler,
    command,
    prefix_command,
)
from xontrib.xgit.cmds import (
    git_cd, git_pwd, git_ls,
)

__all__ = (  # noqa: RUF022
    "_load_xontrib_",
    "_unload_xontrib_",
    "git_cd",
    "git_pwd",
    "git_ls",
    "ObjectId",
    "CommitId",
    "TreeId",
    "BlobId",
    "TagId",
    "GitException",
    "GitError",
    "GitValueError",
    "RepositoryNotFoundError",
    "WorktreeNotFoundError",
    "GitNoWorktreeException",
    "GitNoRepositoryException",
    "GitId",
    "GitObject",
    "GitBlob",
    "GitTree",
    "GitCommit",
    "GitTagObject",
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
    "Note",
    "RemoteBranch",
    "Replacement",
    "DirectoryKind",
    "path_and_parents",
    "pre",
    "post",
    "prepost",
    "print_if",
    "relative_to_home",
    "shorten_branch",
    "View",
    "ViewConfig",
    "MultiView",
    "TableView",
    "Column",
    "ColumnKeys",
    "ColumnDict",
    "HeadingStrategy",
    "ExtractorFnMulti",
    "ExtractorFn",
    "Invoker",
    "SharedSessionInvoker",
    "EventInvoker",
    "CommandInvoker",
    "Command",
    "PrefixCommandInvoker",
    "Runner",
    "SharedSessionRunner",
    "EventRunner",
    "PrefixCommand",
    "session",
    "event_handler",
    "command",
    "prefix_command",
)
