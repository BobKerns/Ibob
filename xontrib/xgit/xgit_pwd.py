'''
The xgit pwd command.
'''
from pathlib import Path

from xontrib.xgit.context_types import GitContext
from xontrib.xgit.decorators import command, session, xgit
from xontrib.xgit.context import _relative_to_home
from xontrib.xgit.types import GitNoRepositoryException

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'pwd'),
)
@session()
def git_pwd(*, XGIT: GitContext):
    """
    Print the current working directory and git context information if available.
    """
    try:
        XGIT.repository
    except GitNoRepositoryException:
        print(f"cwd: {_relative_to_home(Path.cwd())}")
        print("Not in a git repository")
        return
    return XGIT
