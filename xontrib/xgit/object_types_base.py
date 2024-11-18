'''
Common base for all object types and the entry types that reference them.

Separated out to avoid circular imports.

BEWARE: The interrelationships between the entry, object, and context
classes are complex. It is very easy to end up with circular imports.
'''


from abc import abstractmethod
from typing import Optional, Protocol, TypeAlias, runtime_checkable

from xontrib.xgit.types import CleanupAction, GitHash, GitObjectType


@runtime_checkable
class GitId(Protocol):
    """
    Anything that has a hash in a git repository.
    """
    @abstractmethod
    def __init__(self, hash: GitHash,
                 cleanup: Optional[CleanupAction] = None):
        ...
    @property
    @abstractmethod
    def hash(self) -> GitHash:
        ...

@runtime_checkable
class GitObject(GitId, Protocol):
    """
    A git object.
    """
    @property
    @abstractmethod
    def type(self) -> GitObjectType:
        ...
    @property
    @abstractmethod
    def size(self) -> int:
        ...
