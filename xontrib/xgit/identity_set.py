'''
A set of objects compared for identity rather than equality

Adapted amd modernized from:
https://stackoverflow.com/questions/16994307/identityset-in-python
'''

from collections.abc import MutableSet
from typing import Callable, Generic, TypeVar


E = TypeVar('E')
K = TypeVar('K')
class IdentitySet(Generic[E, K], MutableSet):
    __key: Callable[[object],K] # should return a hashable object
    @property
    def key(self):
        return self.__key

    __map: dict[object, E]
    def __init__(self, iterable=(), key: Callable[[object], K]=id):
        self.__key = key
        self.__map = {} # id -> object
        self |= iterable  # add elements from iterable to the set (union)

    def __len__(self):  # Sized
        return len(self.__map)

    def __iter__(self):  # Iterable
        return iter(self.__map.values())

    def __contains__(self, x: object):  # Container
        return self.__key(x) in self.__map

    def add(self, value):  # MutableSet
        """Add an element."""
        self.__map[self.__key(value)] = value

    def discard(self, value):  # MutableSet
        """Remove an element.  Do not raise an exception if absent."""
        self.__map.pop(self.__key(value), None)

    def __repr__(self):
        if not self:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({list(self)!r})'