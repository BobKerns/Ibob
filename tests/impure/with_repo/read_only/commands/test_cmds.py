'''
Test the XGit commands.
'''

from typing import Any, cast

from pytest import raises
def test_ls(clean_modules, git_context, repository, chdir):
    '''
    Test the xgit ls command.
    '''
    from xontrib.xgit.xgit_ls import git_ls
    chdir(repository.path.parent)

    with raises(Exception) as exc:
        git_ls(XGIT=git_context)
    assert exc.typename == 'GitNoWorktreeException'

def test_ls_cmd(git_context, xonsh_session, worktree):
    '''
    Test the xgit ls command.
'''
    from xontrib.xgit.xgit_ls import git_ls
    git_context.worktree = worktree
    runner = cast(Any, git_ls).create_runner(
        _export=lambda func, name: None,
        _exports={},
    )
    runner.inject(XGIT=git_context, XSH=xonsh_session)
    runner([])