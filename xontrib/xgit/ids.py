'''
Basic ID types. Split out for downrev handling w/o introducing circular imports.
'''

from typing import NewType


ObjectId = NewType('ObjectId', str)
'''
A git hash. Defined as a string to make the code more self-documenting.

Also allows using `GitHash` as a type hint that drives completion.
'''
CommitId = NewType('CommitId', ObjectId)
TagId = NewType('TagId', ObjectId)
TreeId = NewType('TreeId', ObjectId)
BlobId = NewType('BlobId', ObjectId)


GitRepositoryId = NewType('GitRepositoryId', str)
"""
A unique identifier for a git repository.
"""