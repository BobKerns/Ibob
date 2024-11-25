'''
The xgit ls command.
'''
from pathlib import Path, PurePosixPath
from typing import cast

from xontrib.xgit.context_types import GitContext
from xontrib.xgit.decorators import command, session, xgit
from xontrib.xgit.object_types import GitObject, GitTree
from xontrib.xgit.entry_types import GitEntry, GitEntryTree, EntryObject
from xontrib.xgit.view import View
from xontrib.xgit.table import TableView

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'ls'),
    flags={'table'}
)
def git_ls(path: Path | str = Path('.'), /, *,
           XGIT: GitContext,
           table: bool=False,
           **_) -> GitEntry[EntryObject]|View:
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
        parent: GitObject  = XGIT.commit
        tree = parent.tree
        for part in path.parent.parts:
            if part == ".":
                continue
            entry = tree.get(part)
            if not isinstance(entry, GitEntryTree):
                raise ValueError(f"{path} is not a directory: {type(entry)}")
            entry = entry.object[part]
            path = path / part
            tree = entry.object.as_('tree')
        tree = cast(GitTree, tree)
        return tree.get(path.name)
    val = do_ls(git_path)
    if table:
        val = TableView(val)
    return val
