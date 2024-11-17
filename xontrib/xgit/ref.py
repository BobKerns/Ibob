'''
Any ref, usually a branch or tag, usually pointing to a commit.
'''

from typing import Any, Optional

from xonsh.lib.pretty import PrettyPrinter

from xontrib.xgit.to_json import JsonDescriber, JsonData
from xontrib.xgit.git_types import (
    GitObject, GitRef, RemoteBranch, Branch, Tag,
)
from xontrib.xgit.objects import _git_object
from xontrib.xgit.procs import _run_text

class _GitRef(GitRef):
    '''
    Any ref, usually a branch or tag, usually pointing to a commit.
    '''
    _name: str
    @property
    def name(self) -> str:
        if self._name in ('HEAD', 'MERGE_HEAD', 'ORIG_HEAD', 'FETCH_HEAD'):
            # Dereference on first use.
            self._name = _run_text(['git', 'symbolic-ref', self._name])
        return self._name

    _target: GitObject|None = None
    @property
    def target(self) -> GitObject:
        if self._target is None:
            target = _run_text(['git', 'show_ref', '--hash', self.name])
            if not target:
                raise ValueError(f"Ref not found: {self.name!r}")
            self._target = _git_object(target)
        return self._target

    def __init__(self, name: str, /, *,
                 no_exists_ok: bool=False,
                 no_check: bool=False,
                 target: Optional[str|GitObject]=None):
        '''
        Initialize a ref. If `no_exists_ok` is `True`. the ref is not checked
        for existence, but is checked for validity and normalized.

        If `no_check` is `True`, the ref is not checked for validity, but is
        assumed to come from a trusted source such as `git show-ref`.

        If `target` is provided, it is used as the target.
        Otherwise the target is resolved from the ref on demand and cached.
        '''
        if name in ('HEAD', 'MERGE_HEAD', 'ORIG_HEAD', 'FETCH_HEAD'):
            # Dereference on first use.
            self._name = name
            return
        else:
            if not no_check:
                _name = _run_text(['git', 'check-ref-format', '--normalize', name])
                if not _name:
                    # Try it as a branch name
                    _name = _run_text(['git', 'check-ref-format', '--branch', name])
                if not _name:
                    raise ValueError(f"Invalid ref name: {name!r}")
            if no_exists_ok:
                self._name = name
            else:
                result = _run_text(['git', 'show-ref', '--verify', name])
                if not result:
                    result = _run_text(['git', 'show-ref', '--verify', f'refs/heads/{name}'])
                if not result:
                    raise ValueError(f"Ref not found: {name!r}")
                target, name = result.split()
        if target is not None:
            if isinstance(target, str):
                self._target = _git_object(target)
            else:
                self._target = target
        self._name = name
        
        if name.startswith('refs/heads/'):
            self.__class__ = _Branch
        elif name.startswith('refs/tags/'):
            self.__class__ = _Tag
        elif name.startswith('refs/remotes/'):
            self.__class__ = _RemoteBranch
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r}, {self.target!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, GitRef):
            return False
        return self.name == other.name and self.target == other.target

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.name, self.target))

    def __str__(self) -> str:
        return self.name

    def _repr_pretty_(self, p: PrettyPrinter, cycle: bool) -> str:
        try:
            if self._name.startswith('refs/heads/'):
                return f'branch {self._name[11:]} -> {self.target.hash}'
            if self._name.startswith('refs/tags/'):
                return f'tag {self._name[10:]} -> {self.target.hash}'
            if self._name.startswith('refs/remotes/'):
                return f'remote {self._name[13:]} -> {self.target.hash}'
            return f'{self._name} -> {self.target.hash}'
        except ValueError:
            # No valid target.
            return self.name

    def to_json(self, desc: JsonDescriber) -> JsonData:
        return self.name

    @staticmethod
    def from_json(data: JsonData, desc: JsonDescriber):
        match data:
            case str():
                return _GitRef(data)
            case _:
                raise ValueError("Invalid branch in JSON")


class _Branch(Branch, _GitRef):
    def branch_name(self) -> str:
        return self.name[11:]
    
    
class _RemoteBranch(RemoteBranch, _GitRef):
    def remote_branch_name(self) -> str:
        return self.name[13:]
    

class _Tag(Tag, _GitRef):
    def tag_name(self) -> str:
        return self.name[10:]
    
