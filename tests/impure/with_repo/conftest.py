'''
This file contains fixtures that work with an actual repository.
'''


import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, TYPE_CHECKING
from collections.abc import Generator
from yaml import safe_load
from dataclasses import dataclass

import pytest


if TYPE_CHECKING:
    from xontrib.xgit.context_types import GitRepository, GitWorktree

class Metadata(SimpleNamespace):
    '''
    A simple namespace for metadata.
    '''
    def __init__(self, metadata: dict[str, Any]):
        super().__init__(**{k:Metadata(v) if isinstance(v, dict) else v
                          for k,v in metadata.items()})
@dataclass
class MetadataFixture:
    metadata: Metadata

DATA_DIR = Path(__file__).parent / 'data'

@pytest.fixture()
def f_git():
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
            cwd = str(Path(cwd))
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
def f_XGIT(with_xgit):
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
def f_home(tmp_path) -> Generator[Path, None, None]:
    '''
    Fixture to make the top of our test directory hierarchy our $HOME.
    '''
    import os
    from secrets import token_hex

    old_home = os.environ.get('HOME') or str(Path.home())
    home_dir = tmp_path / token_hex(8)
    home_dir.mkdir(parents=False, exist_ok=False)
    os.environ['HOME'] = str(home_dir)
    yield home_dir
    os.environ['HOME'] = old_home


@pytest.fixture()
def f_testdir(f_home) -> Generator[Path, None, None]:
    '''
    Fixture to create a temporary directory.
    '''
    from secrets import token_hex
    test_path: Path = f_home / token_hex(8)
    test_path.mkdir(parents=False, exist_ok=False)
    yield test_path

GIT_CONFIG = '''
[user]
    email =  bogons@bogus.com
    name = Fake Name
'''

@pytest.fixture()
def f_gitconfig(f_home) -> Generator[Path, None, None]:
    '''
    Fixture to create a gitconfig file.
    '''
    gitconfig = f_home / '.gitconfig'
    with gitconfig.open('w') as f:
        f.write(GIT_CONFIG)
    yield gitconfig

@dataclass
class RepositoryPathFixture(MetadataFixture):
    home: Path
    repository_path: Path
    worktree_path: Path
    gitconfig: Path

@pytest.fixture()
def repository_unzipped(
        f_home,
        f_testdir,
        f_gitconfig,
    ) -> Generator[RepositoryPathFixture, None, None]:
    '''
    Fixture to create a test repository.
    '''
    from tests.impure.with_repo.zip_repo import unzip_repo
    from_zip = DATA_DIR / 'test_repo.zip'
    worktree = f_testdir / 'test_repo'
    to_git = worktree / '.git'
    worktree.mkdir(parents=False, exist_ok=False)
    unzip_repo(from_zip, to_git)
    metadata_file = from_zip.with_suffix('.yaml')
    with metadata_file.open() as f:
        metadata = safe_load(f)
    yield RepositoryPathFixture(
        metadata=Metadata(metadata),
        home=f_home,
        repository_path=to_git,
        gitconfig=f_gitconfig,
        worktree_path=worktree,
    )

@dataclass
class RepositoryFixture(RepositoryPathFixture):
    repository: 'GitRepository'

@pytest.fixture()
def f_repo(f_XGIT,
            repository_unzipped,
            ) -> Generator[RepositoryFixture, None, None]:
    '''
    Fixture to create a test repository.
    '''
    unzipped = repository_unzipped
    repository_path = unzipped.repository_path
    repo = f_XGIT.open_repository(repository_path)
    yield RepositoryFixture(
        metadata=unzipped.metadata,
        home=unzipped.home,
        gitconfig=unzipped.gitconfig,
        repository_path=repository_path,
        worktree_path=unzipped.worktree_path,
        repository=repo,
    )


@dataclass
class WorktreeFixture(RepositoryFixture):
    worktree_path: Path
    worktree: 'GitWorktree'

@pytest.fixture()
def f_worktree(
        f_git,
        f_repo,
        f_chdir,
    ) -> Generator[WorktreeFixture, None, None]:
    '''
    Fixture to create a test worktree.
    '''
    worktree_path = f_repo.worktree_path
    f_chdir(worktree_path)
    f_git('reset', '--hard', 'HEAD', cwd=worktree_path)

    worktree = f_repo.repository.open_worktree(worktree_path)
    yield WorktreeFixture(
        metadata=f_repo.metadata,
        home=f_repo.home,
        gitconfig=f_repo.gitconfig,
        repository_path=f_repo.repository_path,
        repository=f_repo.repository,
        worktree_path=worktree_path,
        worktree=worktree
    )
