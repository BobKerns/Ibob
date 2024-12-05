'''
The xgit-cd command.
'''
from pathlib import Path, PurePosixPath
import sys

from xontrib.xgit.decorators import command, xgit

@command(
    export=True,
    prefix=(xgit, 'cd'),
)
def git_cd(path: str = "", *, XSH, XGIT, stderr=sys.stderr) -> None:
    """
    Change the current working directory to the path provided.
    If no path is provided, change the current working directory
    to the git repository root.
    """
    execer = XSH.execer

    fpath = Path() / path
    if path == "":
        XGIT.path = PurePosixPath(".")
        if XGIT.worktree is not None:
            fpath = XGIT.worktree.path
    elif path == ".":
        pass
    else:
        try:
            loc = (XGIT.worktree.location / XGIT.path / path).resolve()
            git_path = PurePosixPath(loc.relative_to(XGIT.worktree.location))
            XGIT.path = git_path
            fpath = XGIT.worktree.path / XGIT.path
        except ValueError:
            # Leaving the worktree
            pass
    try:
        execer.exec(f"cd {fpath}")
    except Exception as ex:
        print(f"Could not change to {fpath}: {ex}", file=stderr)
