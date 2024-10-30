"""
Convenient interactive extensions to basic datatypes.
"""

from typing import Optional, Any
from pathlib import Path
from re import Pattern

type ClassKeyElt = str|type|None
type ClassKey = tuple[type, *tuple[ClassKeyElt,...]]

_class_cache: dict[ClassKey,type] = {}

def _get_class(typ: type, *args: ClassKeyElt) -> type|None:
    key: ClassKey = (typ, *args)
    if key in _class_cache:
        return _class_cache[key]
    return None

def _set_class(cls: type, typ: type, *args: ClassKeyElt) -> type:
    key: ClassKey = (typ, *args)
    _class_cache[key] = cls
    return typ

class _Meta(type):
    def __repr__(self):
        return self.__name__

def _bstring_cls(word_sep: Optional[str]=None) -> type:
    cls = _get_class(str, word_sep)
    if cls:
        return cls
    class BStr(str, metaclass=_Meta):
        def _split(self):
            match word_sep:
                case None:
                    return blist([bstring(s, ':') for s in self.split()], ':')
                case Pattern():
                    return blist([bstring(s, ':') for s in word_sep.split(self)], ':')
                case _:
                    return blist([bstring(s, '/') for s in self.split(word_sep)], '/')
        s = property(_split)
        
        def _splitlines(self):
            return blist([bstring(s) for s in self.strip().splitlines()])
        
        l = property(_splitlines)
        
        def _path(self):
            try:
                return Path(self)
            except Exception:
                return self
            
        p = property(_path)
    if word_sep:
        BStr.__name__ = f'BStr[{word_sep}]'
    else:
        BStr.__name__ = 'BStr[]'
    _set_class(BStr, str, word_sep)
    return BStr

def bstring(s: Any, word_sep: Optional[str]=None) -> str:
    match s:
        case list():
            return [bstring(x, word_sep) for x in s]
        case set():
            return {bstring(x, word_sep) for x in s}    
    cls = _bstring_cls(word_sep)
    return cls(str(s))

def _blist_cls(word_sep: Optional[str]=None) -> type:
    cls = _get_class(list, word_sep)
    if cls:
        return cls
    class BList(list, metaclass=_Meta):
        def __split(self):
            return blist([bstring(s, word_sep) for s in self])
        s = property(__split)
        
        def __splitlines(self):
            return blist([bstring(s, word_sep) for s in self])
        l = property(__splitlines)
        
        def __path(self):
            def __path_2(p: str):
                try:
                    return Path(p)
                except Exception:
                    return p
            return blist([__path_2(p) for p in self])
        p = property(__path)
        x = property(set)
    if word_sep:
        BList.__name__ = f'BList[{word_sep}]'
    else:
        BList.__name__ = 'BList[]'
    _set_class(BList, list, word_sep)
    return BList

def blist(l: Any, word_sep: Optional[str]=None) -> list:
    match l:
        case list():
            l = [bstring(s, word_sep) for s in l]
        case set():
            l = {bstring(s, word_sep) for s in l}
        case _:
            return bstring(l, word_sep).l
    cls = _blist_cls(word_sep)
    return cls(l)

def _bset_cls(word_sep: Optional[str]=None) -> type:
    cls = _get_class(set, word_sep)
    if cls:
        return cls
    class BSet(set, metaclass=_Meta):
        def __split(self):
            return bset([bstring(s, word_sep) for s in self])
        s = property(__split)
        
        def __splitlines(self):
            return bset([bstring(s, word_sep) for s in self])
        l = property(__splitlines)
        
        def __path(self):
            def __path_2(p: str):
                try:
                    return Path(p)
                except Exception:
                    return p
            return blist([__path_2(p) for p in self])
        p = property(__path)
        x = property(list)
    if word_sep:
        BSet.__name__ = f'BSet[{word_sep}]'
    else:
        BSet.__name__ = 'BSet[]'
    _set_class(BSet, set, word_sep)
    return BSet
        
def bset(l: set, word_sep: Optional[str]=None) -> list:
    cls = _bset_cls(word_sep)
    return cls(l)