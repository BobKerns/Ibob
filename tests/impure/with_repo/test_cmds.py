'''
Test the XGit commands.
'''

from pathlib import Path
from typing import Any, MutableMapping, cast

from pytest import raises
from xonsh.built_ins import XonshSession

def test_pwd_no_repo(git_context, worktree, capsys, chdir, sysdisplayhook):
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

def test_ls(clean_modules, git_context, repository):
    '''
    Test the xgit ls command.
    '''
    from xontrib.xgit.xgit_ls import git_ls
    from xontrib.xgit.types import GitNoWorktreeException
    with raises(GitNoWorktreeException):
        git_ls(XGIT=git_context)

def test_ls_cmd(git_context, worktree):
    '''
    Test the xgit ls command.
'''
    from xontrib.xgit.xgit_ls import git_ls
    git_context.worktree = worktree
    cast(Any, git_ls).command([])