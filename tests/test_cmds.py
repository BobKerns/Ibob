'''
Test the XGit commands.
'''

from pathlib import Path
from typing import MutableMapping

from xonsh.built_ins import XonshSession

def test_pwd_no_repo(with_xgit, capsys, chdir):
    '''
    Test the xsh proxy.
    '''
    def _t(*_, git_pwd, **__) -> None:
        root = Path('/').resolve()
        chdir(root)
        git_pwd()
        output = capsys.readouterr()
        lines = output.out.strip().split('\n')
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"
        assert lines[0] == f'cwd: {root}'
        assert lines[1] == 'Not in a git repository'
    with_xgit(_t)

def test_ls(with_xgit,
            repository):
    '''
    Test the xgit ls command.
    '''
    def _t(*_, git_ls, **__) -> None:
        git_ls()
    with_xgit(_t,
              'xontrib.xgit.xgit_ls',
              )

def test_ls_cmd(with_xgit):
    '''
    Test the xgit ls command.
    '''
    def _t(*_, git_ls, **__) -> None:
        info = git_ls.info
        info.wrapper([])
    with_xgit(_t, 'xontrib.xgit.xgit_ls')