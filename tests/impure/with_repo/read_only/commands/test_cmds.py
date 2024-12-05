'''
Test the XGit commands.
'''

from pathlib import PurePosixPath
from typing import cast

from pytest import raises

from xontrib.xgit.invoker import CommandInvoker
def test_ls(f_XGIT, f_repo, f_chdir):
    '''
    Test the xgit ls command.
    '''
    from xontrib.xgit.xgit_ls import git_ls
    f_chdir(f_repo.repository_path.parent)

    with raises(Exception) as exc:
        git_ls(XGIT=f_XGIT)
    assert exc.typename == 'GitNoWorktreeException'

def test_ls_cmd(f_XGIT, xonsh_session, f_worktree):
    '''
    Test the xgit ls command.
'''
    from xontrib.xgit.xgit_ls import git_ls
    from xontrib.xgit.entries import _GitEntry

    f_XGIT.worktree = f_worktree.worktree
    runner = cast(CommandInvoker, git_ls).create_runner(
        _export=lambda func, name: None,
        _exports={},
    )
    runner.inject(XGIT=f_XGIT, XSH=xonsh_session)
    value = runner([])
    tree = f_worktree.metadata.ids.tree
    assert isinstance(value, _GitEntry)
    assert value.hash == tree # '4d5fcadc293a348e88f777dc0920f11e7d71441c'
    assert value.type == 'tree'
    assert value.name == '.'
    assert value.path == PurePosixPath('.')
