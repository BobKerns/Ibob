'''
The xgit ls command.
'''
from pathlib import Path
from typing import cast

from xonsh.tools import chdir

from xontrib.xgit.vars import XGIT
from xontrib.xgit.decorators import command, xgit
from xontrib.xgit.objects import _git_entry, _git_object
from xontrib.xgit.git_types import GitTree, GitObject
from xontrib.xgit.procs import _run_stdout

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'ls'),
)
def git_ls(path: Path | str = Path('.')) -> GitTree:
    """
    List the contents of the current directory or the directory provided.
    """
    if not XGIT:
        raise ValueError("Not in a git repository")
    worktree = XGIT.worktree.path
    dir = worktree / XGIT.path / Path(path)
    path = dir.relative_to(worktree)
    def do_ls(path: Path) -> GitTree:
        if path == Path("."):
            tree = _run_stdout(
                ["git", "log", "--format=%T", "-n", "1", "HEAD"]
            )
            parent: GitObject  = _git_object(_run_stdout(['git', 'rev-parse', 'HEAD']), 'commit')
        else:
            path_parent = path.parent
            if path_parent != path and path != Path("."):
                parent = do_ls(path.parent)
                tree = parent[path.name].hash

        if not XGIT:
            raise ValueError("Not in a git repository")
        _, dir = _git_entry(tree, path.name, "040000", "tree", "-", XGIT,
                            parent=parent or XGIT.worktree.commit)
        return cast(GitTree, dir.object)
    if dir.is_dir():
        with chdir(dir):
            return do_ls(path)
    elif dir.is_file():
        with chdir(dir.parent):
            return do_ls(path)
    else:
        with chdir(worktree):
            return do_ls(path)

