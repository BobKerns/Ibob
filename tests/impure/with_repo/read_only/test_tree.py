'''
Tests of the tree objects and their entries.
'''

from pathlib import PurePosixPath

def test_get_tree_root(f_repo):
    '''
    Test getting the root tree object from the branch and commit.
    '''
    repo = f_repo.repository
    meta = f_repo.metadata
    head = repo.get_ref('refs/heads/main')
    tree = head.target.tree
    assert tree is not None
    assert tree.type == 'tree'
    assert tree.hash  == meta.ids.tree


def test_get_tree_entry(f_repo):
    '''
    Test getting a tree entry from the tree.
    '''

    repo = f_repo.repository
    meta = f_repo.metadata
    head = repo.get_ref('refs/heads/main')
    tree = head.target.tree
    entry = tree.get('.')
    assert entry is not None
    assert entry.name == '.'
    assert entry.path == PurePosixPath('.')
    assert entry.hash == meta.ids.tree
    assert entry.type == 'tree'
    foo = tree.get('foo')
    assert foo is not None


def test_tree_entry_get(f_repo):
    '''
    Test getting a tree entry from a tree entry.
    '''

    repo = f_repo.repository
    meta = f_repo.metadata
    head = repo.get_ref('refs/heads/main')
    tree = head.target.tree
    entry = tree['.']
    assert entry is not None
    assert entry.name == '.'
    assert entry.path == PurePosixPath('.')
    assert entry.hash == meta.ids.tree
    assert entry.type == 'tree'