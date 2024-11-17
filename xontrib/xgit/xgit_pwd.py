'''
The xgit pwd command.
'''
from pathlib import Path

from xontrib.xgit.vars import XGIT
from xontrib.xgit.decorators import command, xgit
from xontrib.xgit.context import _relative_to_home
from xontrib.xgit.proxy import target

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'pwd'),
)
def git_pwd():
    """
    Print the current working directory and git context information if available.
    """
    if not XGIT:
        print(f"cwd: {_relative_to_home(Path.cwd())}")
        print("Not in a git repository")
        return
    return target(XGIT)
