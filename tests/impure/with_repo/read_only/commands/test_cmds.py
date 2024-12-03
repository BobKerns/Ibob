'''
Test the XGit commands.
'''

from pathlib import Path
from typing import Any, cast
import sys

from pytest import raises

def test_pwd_no_repo(git_context, worktree, capsys, chdir, xonsh_session):
    '''
    Test the XGIT context as showing where we are..
    '''
    from xontrib.xgit.xgit_pwd import git_pwd
    root = worktree.location.parent.resolve()
    chdir(worktree.location.parent)
    git_context.worktree = None
    git_context.repository = None
    git_pwd(XGIT=git_context,
            XSH=xonsh_session,
            stderr=sys.stderr,
            stdout=sys.stdout,
            stdin=sys.stdin)
    output = capsys.readouterr()
    lines = output.out.strip().split('\n')

    if len(lines) > 0:
        def shorten_path(p: Path):
            p = p.relative_to(Path.home())
            return Path('~') / p
        assert lines[0] == f'cwd: {shorten_path(root)}'
    if len(lines) > 1:
        assert lines[1] == 'Not in a git repository'
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"

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