'''
The xgit ls command.
'''
from pathlib import Path
from typing import cast

from xonsh.tools import chdir

from xontrib.xgit.vars import XGIT
from xontrib.xgit.decorators import command, xgit
from xontrib.xgit.objects import _git_entry, _git_object
from xontrib.xgit.object_types import GitTree, GitObject
from xontrib.xgit.entry_types import GitEntryTree
from xontrib.xgit.view import View
from xontrib.xgit.table import TableView

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'ls'),
    flags={'table'}
)
def git_ls(path: Path | str = Path('.'), /, *, table: bool=False) -> GitEntryTree|View:
    """
    List the contents of the current directory or the directory provided.
    """
    if not XGIT:
        raise ValueError("Not in a git repository")
    worktree = XGIT.worktree
    repository = worktree.repository
    dir = worktree.path / XGIT.path / Path(path)
    path = dir.relative_to(worktree.path)
    def do_ls(path: Path) -> GitEntryTree:

        if path == Path("."):
            tree = worktree.git("log", "--format=%T", "-n", "1", "HEAD")
            parent_rev = worktree.git("rev-parse", "HEAD")
            parent: GitObject  = _git_object(parent_rev, repository, 'commit')
        else:
            path_parent = path.parent
            if path_parent != path and path != Path("."):
                parent = cast(GitTree, do_ls(path.parent).object)
                tree = parent[path.name].hash

        if not XGIT:
            raise ValueError("Not in a git repository")
        _, entry = _git_entry(tree, path.name, "040000", "tree", "-",
                            repository=repository,
                            parent=parent or XGIT.worktree.commit)
        return entry
    val = do_ls(path)
    if table:
        val = TableView(val)
    return val


