'''
This file contains fixtures that work with an actual repository.
'''


import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from collections.abc import Generator
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
def git_context(with_xgit):
    '''
    Fixture to create a test context.
    '''
    if (xgit := with_xgit.XSH.env.get('XGIT')) is not None:
        yield xgit
        return
    context = with_xgit.module._GitContext(with_xgit.XSH)
    with_xgit.XSH.env['XGIT'] = context
    yield context

@pytest.fixture()
def test_dir(tmp_path) -> Path:
    '''
    Fixture to create a temporary directory.
    '''
    from secrets import token_hex
    tmp_path = tmp_path / token_hex(16)
    tmp_path.mkdir(parents=False, exist_ok=False)
    return tmp_path

@pytest.fixture()
def home_dir(tmp_path) -> Generator[Path, None, None]:
    '''
    Fixture to make the top of our test directory hierarchy our $HOME.
    '''
    import os
    old_home = os.environ.get('HOME') or str(Path.home())
    os.environ['HOME'] = str(tmp_path)
    yield tmp_path
    os.environ['HOME'] = old_home

GIT_CONFIG = '''
[user]
    email =  bogons@bogus.com
    name = Fake Name
'''

@pytest.fixture()
def gitconfig(home_dir) -> Generator[Path, None, None]:
    '''
    Fixture to create a gitconfig file.
    '''
    gitconfig = home_dir / '.gitconfig'
    with gitconfig.open('w') as f:
        f.write(GIT_CONFIG)
    yield gitconfig

@pytest.fixture()
def repository_unzipped(
               git_context,
               test_dir,
               gitconfig,
               ) -> Generator[Path, None, None]:
    '''
    Fixture to create a test repository.
    '''
    from tests.impure.with_repo.zip_repo import unzip_repo
    from_zip = DATA_DIR / 'test_repo.zip'
    worktree = test_dir / 'test_repo'
    to_git = worktree / '.git'
    worktree.mkdir(parents=False, exist_ok=False)
    unzip_repo(from_zip, to_git)
    yield to_git

@pytest.fixture()
def repository(git_context,
               repository_unzipped,
               ) -> Generator['GitRepository', None, None]:
    '''
    Fixture to create a test repository.
    '''
    yield git_context.open_repository(repository_unzipped)

@pytest.fixture()
def worktree(
    git,
    repository,
    chdir,
    ) -> Generator['GitWorktree', None, None]:
    '''
    Fixture to create a test worktree.
    '''
    #from xontrib.xgit.worktree import _GitWorktree
    #from xontrib.xgit.ref import _GitRef
    #from xontrib.xgit.objects import _GitCommit
    worktree = repository.path.parent
    chdir(worktree)
    git('reset', '--hard', 'HEAD', cwd=worktree)
    yield  repository.open_worktree(worktree)