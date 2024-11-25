'''
Tests for the `GitPath` class.
'''

from pathlib import PurePath
import pytest

def test_create_git_path(repository):
    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    commit_id = repository.rev_parse('HEAD')
    commit = _GitCommit(commit_id, repository=repository)
    base = PathBase(
                repository=repository,
                top=commit.tree,
                root_object=commit,
                root=None,
                origin=commit)
    p = GitPath(
        object=commit.tree,
        base=base,
        )

    assert type(p) == GitPath
    assert isinstance(p, PurePath)
    assert p.object == commit.tree
    assert p.repository == repository

def test_create_git_path_unrooted(repository):

    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    commit_id = repository.rev_parse('HEAD')
    commit = _GitCommit(commit_id, repository=repository)
    base = PathBase(
                repository=repository,
                top=commit.tree,
                root=None,
                root_object=commit,
                origin=None)
    p = GitPath(
            base=base,
            object=commit.tree)

    assert type(p) == GitPath
    assert isinstance(p, PurePath)
    assert p.object == commit.tree
    assert p.repository == repository