'''
Tests for the `GitPath` class.
'''

from pathlib import PurePath

def test_create_git_path(f_repo):
    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    repository = f_repo.repository
    
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

    assert type(p) is GitPath
    assert isinstance(p, PurePath)
    assert p.object == commit.tree
    assert p.repository == repository

def test_create_git_path_unrooted(f_repo):
    from xontrib.xgit.git_path import GitPath, PathBase
    from xontrib.xgit.objects import _GitCommit
    repository = f_repo.repository

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

    assert type(p) is GitPath
    assert isinstance(p, PurePath)
    assert p.object == commit.tree
    assert p.repository == repository