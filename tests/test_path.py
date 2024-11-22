'''
Tests for the `GitPath` class.
'''

from pathlib import PurePosixPath
import pytest

def test_create_git_path(repository):
    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    commit_id = repository.git('rev-parse', 'HEAD')
    commit = _GitCommit(commit_id, repository=repository)
    base = PathBase(
                repository=repository,
                top=commit.tree,
                root=commit,
                origin=commit)
    p = GitPath(
        object=commit.tree,
        base=base,
        path=PurePosixPath())

    assert type(p) == GitPath
    assert isinstance(p, PurePosixPath)
    assert p.object == commit.tree
    assert p.repository == repository

def test_create_git_path_unrooted(repository):

    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    commit_id = repository.git('rev-parse', 'HEAD')
    commit = _GitCommit(commit_id, repository=repository)
    base = PathBase(
                repository=repository,
                top=commit.tree,
                root=None,
                origin=None)
    p = GitPath(
            base=base,
            path=PurePosixPath(),
            object=commit.tree)

    assert type(p) == GitPath
    assert isinstance(p, PurePosixPath)
    assert p.object == commit.tree
    assert p.repository == repository