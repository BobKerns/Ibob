'''
The xgit pwd command.
'''
from pathlib import Path

from xontrib.xgit.context_types import GitContext
from xontrib.xgit.decorators import command, xgit
from xontrib.xgit.context import _relative_to_home

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'pwd'),
)
def git_pwd(*, XGIT: GitContext, stdout, **_):
    """
    Print the current working directory and git context information if available.
    """
    try:
        return XGIT.repository
    except Exception as ex:
        if type(ex).__name__ == 'GitNoRepositoryException':
            print(f"cwd: {_relative_to_home(Path.cwd())}", file=stdout)
            print("Not in a git repository", file=stdout)
            return
        raise ex
    return XGIT
