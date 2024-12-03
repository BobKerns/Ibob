'''
Various worktree-related tests.
'''

from pathlib import Path, PurePosixPath

import pytest

def test_worktree_fixture(worktree):
    '''
    Test the worktree fixture.
    '''
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
    # For primary worktrees.
    assert repository.path == worktree.repository_path
    assert repository.worktrees is not None
    assert worktree.location in repository.worktrees

def test_open_worktree(git_context):
    '''
    Test opening a worktree.
    '''
    worktree = git_context.open_worktree(Path('.'))
    assert worktree is not None
    assert worktree.path == PurePosixPath('.')
    assert worktree.location == Path('.').resolve()
    # Invalid in seperate worktrees.
    #assert worktree.repository_path == Path('.git').resolve()
    assert worktree.repository_path.exists()
    assert worktree.repository_path.is_dir

def test_open_worktree_no_repo(with_xgit, git_context):
    '''
    Test opening a worktree without a repository.
    '''
    with pytest.raises(Exception) as exc:
        if exc.typename != 'RepositoryNotFoundError':
            raise exc.value
        git_context.open_worktree(Path('/'))

def test_open_worktree_open_repo(git_context):
    '''
    Test opening a worktree with an open repository.
    '''
    pass
