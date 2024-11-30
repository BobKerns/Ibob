'''
Test the XGit commands.
'''

from pathlib import Path
from typing import Any, cast

from pytest import raises
import xonsh
def test_pwd_no_repo(git_context, worktree, capsys, chdir):
    '''
    Test the xsh proxy.
    '''
    from xontrib.xgit.xgit_pwd import git_pwd
    root = Path('/').resolve()
    chdir(worktree.location.parent)
    git_pwd(XGIT=git_context)
    output = capsys.readouterr()
    lines = output.out.strip().split('\n')

    if len(lines) > 0:
        assert lines[0] == f'cwd: {root}'
    if len(lines) > 1:
        assert lines[1] == 'Not in a git repository'
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"

def test_ls(clean_modules, git_context, repository, chdir):
    '''
    Test the xgit ls command.
    '''
    from xontrib.xgit.xgit_ls import git_ls
    from xontrib.xgit.types import GitNoWorktreeException
    chdir(repository.path.parent)

    with raises(GitNoWorktreeException):
        git_ls(XGIT=git_context)

def test_ls_cmd(git_context, xonsh_session, worktree):
    '''
    Test the xgit ls command.
'''
    from xontrib.xgit.xgit_ls import git_ls
    git_context.worktree = worktree
    runner = cast(Any, git_ls).create_runner(
        _aliases={},
        _export=lambda func, name: None,
        _exports={},
    )
    runner.inject({'XGIT': git_context, 'XSH': xonsh_session})
    runner([])