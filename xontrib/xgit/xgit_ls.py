'''
The xgit ls command.
'''
from pathlib import Path, PurePosixPath
from tkinter import Entry
from typing import cast

from xonsh.tools import chdir

from xontrib.xgit.vars import XGIT
from xontrib.xgit.decorators import command, xgit
from xontrib.xgit.objects import _git_entry, _git_object
from xontrib.xgit.object_types import GitObject
from xontrib.xgit.entry_types import GitEntry, GitEntryTree, EntryObject
from xontrib.xgit.view import View
from xontrib.xgit.table import TableView

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'ls'),
    flags={'table'}
)
def git_ls(path: Path | str = Path('.'), /, *, table: bool=False) -> GitEntry[EntryObject]|View:
    """
    List the contents of the current directory or the directory provided.
    """
    if not XGIT:
        raise ValueError("Not in a git repository")
    worktree = XGIT.worktree
    repository = worktree.repository
    dir = worktree.path / XGIT.path / Path(path)
    git_path = PurePosixPath(dir.relative_to(worktree.path))
    def do_ls(path: PurePosixPath) -> GitEntry[EntryObject]:
        tree = worktree.git("log", "--format=%T", "-n", "1", "HEAD")
        parent_rev = worktree.git("rev-parse", "HEAD")
        parent: GitObject  = _git_object(parent_rev, repository, 'commit')
        entry: GitEntry[EntryObject]
        _, entry = _git_entry(tree, '.', "040000", "tree", "-",
                        repository=repository,
                        parent=parent)
        for part in path.parts:
            if part == ".":
                continue
            tree = entry.hash
            if not isinstance(entry, GitEntryTree):
                raise ValueError(f"{path} is not a directory: {type(entry)}")
            entry = entry.object[part]
            path = path / part
        return entry
    val = do_ls(git_path)
    if table:
        val = TableView(val)
    return val


