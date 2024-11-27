'''
Various worktree-related tests.
'''

from pathlib import Path, PurePath, PurePosixPath

import pytest

def test_open_worktree(git_context):
    '''
    Test opening a worktree.
    '''
    worktree = git_context.open_worktree(Path('.'))
    assert worktree is not None
    assert worktree.path == PurePosixPath('.')
    assert worktree.location == Path('.').resolve()
    assert worktree.repository_path == Path('.git').resolve()
    assert worktree.repository_path.exists()
    assert worktree.repository_path.is_dir

def test_open_worktree_no_repo(git_context):
    '''
    Test opening a worktree without a repository.
    '''
    from xontrib.xgit.types import RepositoryNotFoundError
    with pytest.raises(RepositoryNotFoundError):
        git_context.open_worktree(Path('/'))

def test_open_worktree_open_repo(git_context):
    '''
    Test opening a worktree with an open repository.
    '''
    pass
