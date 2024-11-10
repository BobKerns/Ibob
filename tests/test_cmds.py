'''
Test the XGit commands.
'''

from pathlib import Path
from typing import MutableMapping

from xonsh.built_ins import XonshSession


def test_pwd(with_xgit, capsys, chdir):
    '''
    Test the xsh proxy.
    '''
    def _t(*_, XSH: XonshSession, git_pwd, **__):
        chdir(Path('/'))
        git_pwd()
        output = capsys.readouterr()
        env = XSH.env
        assert isinstance(env, MutableMapping), \
            f"XSH.env not a MutableMapping {env!r}"

        lines = output.out.strip().split('\n')
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"
        assert lines[0] == 'cwd: /'
        assert lines[1] == 'Not in a git repository'
    with_xgit(_t)