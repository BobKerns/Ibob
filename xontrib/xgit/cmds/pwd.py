'''
The xgit pwd command.
'''
from xontrib.xgit.context_types import GitContext
from xontrib.xgit.decorators import command, xgit

@command(
    for_value=True,
    export=True,
    prefix=(xgit, 'pwd'),
)
def git_pwd(*, XGIT: GitContext, stdout, **_):
    """
    Print the current working directory and git context information if available.
    """
    return XGIT
