'''
Various worktree-related tests.
'''

from pathlib import Path, PurePosixPath

import pytest

def test_worktree_fixture(f_worktree):
    '''
    Test the worktree fixture.
    '''
    worktree = f_worktree.worktree
    assert worktree is not None
    assert isinstance(worktree.path, PurePosixPath)
    assert isinstance(worktree.location,Path)
    assert worktree.location.is_dir()
    assert worktree.repository_path.exists()
    assert worktree.repository_path.is_dir
    # This is a primary worktree.
    assert worktree.repository_path == worktree.location / '.git'
    repository = worktree.repository
    assert repository is not None
    assert repository is f_worktree.repository
    # For primary worktrees.
    assert repository.path == worktree.repository_path
    assert repository.worktrees is not None
    assert worktree.location in repository.worktrees

def test_open_worktree(f_XGIT):
    '''
    Test opening a worktree.
    '''
    worktree = f_XGIT.open_worktree(Path('.'))
    assert worktree is not None
    assert worktree.path == PurePosixPath('.')
    assert worktree.location == Path('.').resolve()
    # Invalid in separate worktrees.
    #assert worktree.repository_path == Path('.git').resolve()
    assert worktree.repository_path.exists()
    assert worktree.repository_path.is_dir

def test_open_worktree_no_repo(f_XGIT):
    '''
    Test opening a worktree without a repository.
    '''
    with pytest.raises(Exception) as exc:
        if exc.typename != 'RepositoryNotFoundError':
            raise exc.value
        f_XGIT.open_worktree(Path('/'))

def test_open_worktree_open_repo(f_XGIT):
    '''
    Test opening a worktree with an open repository.
    '''
    pass # All in the fixtures now.
