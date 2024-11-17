'''
The xgit-cd command.
'''
from pathlib import Path
import sys

from xontrib.xgit.vars import XSH, XGIT
from xontrib.xgit.decorators import command

@command(export=True)
def git_cd(path: str = "", stderr=sys.stderr) -> None:
    """
    Change the current working directory to the path provided.
    If no path is provided, change the current working directory
    to the git repository root.
    """
    execer = XSH.execer
    assert execer is not None, "No execer"
    if not XGIT or XGIT.worktree is None:
        execer.exec(f"cd {path}")
        return
    if path == "":
        XGIT.path = Path(".")
    elif path == ".":
        pass
    else:
        git_path = (XGIT.worktree.path / XGIT.path / path).resolve()
        git_path = git_path.relative_to(XGIT.worktree.path)
        XGIT.path = git_path
    fpath = XGIT.worktree.path / XGIT.path
    try:
        execer.exec(f"cd {fpath}")
    except Exception as ex:
        print(f"Could not change to {fpath}: {ex}", file=stderr)
