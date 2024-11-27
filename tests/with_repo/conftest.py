'''
This file contains fixtures that work with an actual repository.
'''


import os
from pathlib import Path
from threading import RLock
from typing import Generator, Optional, TYPE_CHECKING
import pytest


if TYPE_CHECKING:
    from xontrib.xgit.context_types import GitRepository, GitWorktree

DATA_DIR = Path(__file__).parent / 'data'

@pytest.fixture()
def git():
    '''
    Fixture to run git commands.
    '''
    from subprocess import run, PIPE
    from shutil import which
    _git = which('git')
    if _git is None:
        raise ValueError("git is not installed")
    def git(*args, cwd: Optional[Path|str], check=True, **kwargs):
        if cwd is not None:
            cwd = str(cwd)
        return run([_git, *args],
                   check=check,
                   stdout=PIPE,
                   text=True,
                   env={**os.environ},
                   cwd=cwd,
                   **kwargs
                ).stdout.rstrip()
    return git


@pytest.fixture()
def git_context(with_xgit, xonsh_session):
    '''
    Fixture to create a test context.
    '''
    def _t(*_, XSH, **__):
        from xontrib.xgit.context import _GitContext
        yield _GitContext(xonsh_session)
    yield from with_xgit(_t, 'xontrib.xgit.context')

repository_lock = RLock()
@pytest.fixture()
def repository(
               git_context,
               chdir,
               tmp_path,
               ) -> Generator['GitRepository', None, None]:
    '''
    Fixture to create a test repository.
    '''
    from tests.with_repo.zip_repo import unzip_repo
    from secrets import token_hex
    from shutil import rmtree

    with repository_lock:
        token = token_hex(16)
        from_zip = DATA_DIR / 'test_repo.zip'
        old = Path.cwd()
        old_home = os.environ.get('HOME') or str(Path.home())
        home = tmp_path
        gitconfig = home / '.gitconfig'
        worktree = home / token
        to_git = worktree / '.git'
        worktree.mkdir(parents=False, exist_ok=False)
        unzip_repo(from_zip, to_git)
        os.environ['HOME'] = str(home)
        with gitconfig.open('w') as f:
            f.write('[user]\n\temail = bogons@bogus.com\n\tname = Fake Name\n')
        chdir(worktree)
        yield git_context.open_repository(worktree / '.git')
        chdir(old)
        os.environ['HOME'] = old_home
        # Clean up, or try to: Windows is a pain
        #with suppress(OSError):
        #    rmtree(tmp_path)

@pytest.fixture()
def worktree(
    with_xgit,
    git,
    repository,
    chdir,
    ) -> Generator['GitWorktree', None, None]:
    '''
    Fixture to create a test worktree.
    '''
    def _t(*_, _GitWorktree, _GitCommit, _GitRef, **__):
        from xontrib.xgit.worktree import _GitWorktree
        from xontrib.xgit.ref import _GitRef
        from xontrib.xgit.objects import _GitCommit
        worktree = repository.path.parent
        chdir(worktree)
        git('reset', '--hard', 'HEAD', cwd=worktree)
        yield  repository.open_worktree(worktree)
    yield from with_xgit(_t, 'xontrib.xgit.worktree', 'xontrib.xgit.ref', 'xontrib.xgit.objects')
