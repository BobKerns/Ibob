'''
This file contains fixtures that work with an actual repository.
'''


import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, TYPE_CHECKING, cast
from collections.abc import Generator, Callable
from yaml import safe_load
from dataclasses import dataclass

import pytest


if TYPE_CHECKING:
    from xontrib.xgit.repository import _GitRepository
    from xontrib.xgit.worktree import _GitWorktree
    from xontrib.xgit.context import _GitContext

class Metadata(SimpleNamespace):
    '''
    A simple namespace for metadata.
    '''
    def __init__(self, metadata: dict[str, Any]):
        super().__init__(**{k:Metadata(v) if isinstance(v, dict) else v
                          for k,v in metadata.items()})

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
def f_XGIT(with_xgit) -> '_GitContext':
    '''
    Fixture to create a test context.
    '''
    if (xgit := with_xgit.XSH.env.get('XGIT')) is not None:
        return xgit
    context = with_xgit.module._GitContext(with_xgit.XSH)
    with_xgit.XSH.env['XGIT'] = context
    return context

@pytest.fixture()
def f_home(tmp_path) -> Generator[Path, None, None]:
    '''
    Fixture to make the top of our test directory hierarchy our $HOME.
    '''
    import os
    from secrets import token_hex

    old_home: str = os.environ.get('HOME') or str(Path.home())
    home_dir = tmp_path / token_hex(8)
    home_dir.mkdir(parents=False, exist_ok=False)
    os.environ['HOME'] = str(home_dir)
    yield home_dir
    os.environ['HOME'] = old_home


@pytest.fixture()
def f_testdir(f_home) -> Path:
    '''
    Fixture to create a temporary directory.
    '''
    from secrets import token_hex
    test_path: Path = f_home / token_hex(8)
    test_path.mkdir(parents=False, exist_ok=False)
    return test_path

GIT_CONFIG = '''
[user]
    email =  bogons@bogus.com
    name = Fake Name
'''

@pytest.fixture()
def f_gitconfig(f_home) -> Path:
    '''
    Fixture to create a gitconfig file.
    '''
    gitconfig = f_home / '.gitconfig'
    with gitconfig.open('w') as f:
        f.write(GIT_CONFIG)
    return gitconfig

@dataclass
class RepositoryPathFixture:
    home: Path
    repository_path: Path
    worktree_path: Path
    gitconfig: Path

@pytest.fixture()
def f_repo_paths(
        f_home,
        f_testdir,
        f_gitconfig,
    ) -> RepositoryPathFixture:
    '''
    Fixture to create a test repository.
    '''
    worktree = f_testdir / 'test_repo'
    to_git = worktree / '.git'
    return RepositoryPathFixture(
        home=f_home,
        repository_path=to_git,
        gitconfig=f_gitconfig,
        worktree_path=worktree,
    )


@dataclass
class MetadataFixture(RepositoryPathFixture):
    metadata: Metadata

def expanded_repo(repo: str, paths: RepositoryPathFixture):
    from tests.impure.with_repo.zip_repo import unzip_repo
    from_zip = DATA_DIR / repo
    from_zip = from_zip.with_suffix('.zip')
    to_git = paths.repository_path
    paths.worktree_path.mkdir(parents=False, exist_ok=False)
    unzip_repo(from_zip, to_git)
    metadata_file = from_zip.with_suffix('.yaml')
    with metadata_file.open() as f:
        metadata = safe_load(f)
    return MetadataFixture(
        metadata=Metadata(metadata),
        home=paths.home,
        repository_path=to_git,
        gitconfig=paths.gitconfig,
        worktree_path=paths.worktree_path,
    )


@dataclass
class RepositoryFixture(MetadataFixture):
    repository: '_GitRepository'

@pytest.fixture()
def f_mk_repo(f_XGIT: '_GitContext',
              f_repo_paths,
              ) -> Callable[[str], RepositoryFixture]:
    '''
    Fixture to create a test repository.
    '''
    def mk_repo(repo: str) -> RepositoryFixture:
        unzipped = expanded_repo(repo, f_repo_paths)
        worktree_path = unzipped.worktree_path
        worktree_path = worktree_path.resolve() / repo
        worktree_path.mkdir(parents=False, exist_ok=False)
        repository_path = worktree_path / '.git'
        repository = cast('_GitRepository',f_XGIT.open_repository(repository_path))
        return RepositoryFixture(
            metadata=unzipped.metadata,
            home=unzipped.home,
            gitconfig=unzipped.gitconfig,
            repository_path=repository_path,
            worktree_path=worktree_path,
            repository=repository,
        )
    return mk_repo


@dataclass
class WorktreeFixture(RepositoryFixture):
    worktree: '_GitWorktree'


@pytest.fixture()
def f_mk_worktree(
        f_mk_repo,
        f_git,
        f_chdir,
    ) -> Callable[[str], WorktreeFixture]:
    '''
    Fixture to create a test worktree.
    '''
    def mk_worktree(repo: str) -> WorktreeFixture:
        repo_fixture = f_mk_repo(repo)
        worktree_path = repo_fixture.worktree_path
        f_chdir(worktree_path)
        f_git('reset', '--hard', 'HEAD', cwd=worktree_path)

        worktree = repo_fixture.repository.open_worktree(worktree_path)
        return WorktreeFixture(
            metadata=repo_fixture.metadata,
            home=repo_fixture.home,
            gitconfig=repo_fixture.gitconfig,
            repository_path=repo_fixture.repository_path,
            repository=repo_fixture.repository,
            worktree_path=worktree_path,
            worktree=worktree
        )
    return mk_worktree


@pytest.fixture()
def f_repo(f_mk_repo) -> RepositoryFixture:
    '''
    Fixture to create a test repository.
    '''
    return f_mk_repo('base')


@pytest.fixture()
def f_worktree(f_mk_worktree) -> WorktreeFixture:
    '''
    Fixture to create a test worktree.
    '''
    return f_mk_worktree('base')

@pytest.fixture()
def f_worktree_branch(f_mk_worktree) -> WorktreeFixture:
    '''
    Fixture to create a test worktree.
    '''
    return f_mk_worktree('branch')