'''
Any ref, usually a branch or tag, usually pointing to a commit.
'''

from typing import Any, Callable, Optional

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import ObjectId
from xontrib.xgit.context_types import GitRepository
from xontrib.xgit.views import JsonDescriber, JsonData
import xontrib.xgit.object_types as ot
import xontrib.xgit.ref_types as rt

SYMBOLIC_REFS = frozenset(('HEAD', 'MERGE_HEAD', 'ORIG_HEAD', 'FETCH_HEAD'))
'''
These are not the only symbolic refs, but they are the most common.

They can refer to a ref (typically a branch or tag), or commit.
'''

class _GitRef(rt.GitRef):
    '''
    Any ref, usually a branch or tag, usually pointing to a commit.
    '''
    __name: str
    @property
    def name(self) -> str:
        if self.__name in ('HEAD', 'MERGE_HEAD', 'ORIG_HEAD', 'FETCH_HEAD'):
            repo = self.repository
            # Dereference on first use.
            name = repo.symbolic_ref(self.__name)
            if name:
                self.__name = name
                if self.__validate:
                    self.__validate()
            else:
                # Detached or non-existent ref
                ref = repo.rev_parse(self.__name)
                if ref:
                    self.__target = repo.get_object(ref)
        return self.__name

    __repository: GitRepository
    @property
    def repository(self) -> GitRepository:
        return self.__repository

    __validate: Callable[[], None]|None
    '''
    Allows for delayed validation of the ref name for
    refs obtained from symbolic references.
    '''

    __target: 'ot.GitObject|None' = None
    @property
    def target(self) -> 'ot.GitObject':
        # Fetching the name will trigger validation if needed.
        # Validation will set the target if it's a symbolic ref.
        name = self.name
        if self.__target is None:
            target = ObjectId(self.__repository.git_string('show-ref', '--hash', name))
            if not target:
                raise ValueError(f"Ref not found: {name!r}")
            self.__target = self.__repository.get_object(target)
        return self.__target

    def __init__(self, name: str, /, *,
                 repository: GitRepository,
                 no_exists_ok: bool=False,
                 no_check: bool=False,
                 target: Optional['str|ot.GitObject']=None):
        '''
        Initialize a ref. If `no_exists_ok` is `True`. the ref is not checked
        for existence, but is checked for validity and normalized.

        If `no_check` is `True`, the ref is not checked for validity, but is
        assumed to come from a trusted source such as `git show-ref`.

        If `target` is provided, it is used as the target.
        Otherwise the target is resolved from the ref on demand and cached.
        '''
        self.__name = name
        self.__repository = repository
        def validate():
            nonlocal name
            self.__validate = None
            target = None
            if not no_check:
                _name = repository.git_string('check-ref-format', '--normalize', name,
                                       check=False)
                if not _name:
                    # Try it as a branch name
                    _name = repository.git_string('check-ref-format', '--branch', name,
                                           check=False)
                if not _name:
                    _name = repository.git_string('ref', '--quiet', name,
                                           check=False)
                if not _name and name not in SYMBOLIC_REFS:
                    raise ValueError(f"Invalid ref name: {name!r}")
            if no_exists_ok:
                self.__name = name
            else:
                result = repository.git_string('show-ref', '--verify', name)
                if not result:
                    result = repository.git_string('show-ref', '--verify',
                                                   f'refs/heads/{name}')
                if not result:
                    raise ValueError(f"Ref not found: {name!r}")
                target, name = result.split()
            if target is not None:
                if isinstance(target, str):
                    self.__target = repository.get_object(ObjectId(target))
                else:
                    self.__target = target

        if name.startswith('refs/heads/'):
            self.__class__ = _Branch
        elif name.startswith('refs/tags/'):
            self.__class__ = _Tag
        elif name.startswith('refs/remotes/'):
            self.__class__ = _RemoteBranch
        elif name.startswith('refs/replace/'):
            self.__class__ = _Replacement
            self._replaced = None
        if name in SYMBOLIC_REFS:
            # Dereference on first use.
            self.__name = name
            self.__validate = validate
            return
        else:
            validate()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r}, {self.target!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, 'rt.GitRef'):
            return False
        return self.name == other.name and self.target == other.target

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.name, self.target))

    def __str__(self) -> str:
        return self.name

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool):
        try:
            if self.__name.startswith('refs/heads/'):
                p.text(f'branch {self.__name[11:]} -> {self.target.hash}')
            elif self.__name.startswith('refs/tags/'):
                p.text(f'tag {self.__name[10:]} -> {self.target.hash}')
            elif self.__name.startswith('refs/remotes/'):
                p.text(f'remote {self.__name[13:]} -> {self.target.hash}')
            else:
                p.text(f'ref {self.__name} -> {self.target.hash}')
        except ValueError:
            # No valid target.
            p.text(self.name)

    def to_json(self, desc: JsonDescriber) -> JsonData:
        return self.name

    @staticmethod
    def from_json(data: JsonData, desc: JsonDescriber):
        match data:
            case str():
                return _GitRef(data, repository=desc.repository)
            case _:
                raise ValueError("Invalid branch in JSON")


class _Branch(rt.Branch, _GitRef):
    def branch_name(self) -> str:
        return self.name[11:]


class _RemoteBranch(rt.RemoteBranch, _GitRef):
    def remote_branch_name(self) -> str:
        return self.name[13:]


class _Tag(rt.Tag, _GitRef):
    def tag_name(self) -> str:
        return self.name[10:]

class _Replacement(rt.Replacement, _GitRef):
    _replaced: 'ot.GitObject'
    @property
    def replaced(self) -> 'ot.GitObject':
        '''
        The object being replaced.
        '''
        if self._replaced is None:
            repo = self.__repository
            target = ObjectId(repo.git_string('show-ref', '--hash', self.name))
            if not target:
                raise ValueError(f"Ref not found: {self.name!r}")
            self._replaced = repo.get_object(target)
        return self._replaced

    @property
    def replacement_name(self) -> ObjectId:
        '''
        The Sha1 hash of the object being replaced.
        '''
        return ObjectId(super().name[13:])

class _Note(rt.Note, _GitRef):
    __attached_to: Optional['ot.GitObject']
    @property
    def note_name(self) -> ObjectId:
        return ObjectId(self.name[10:])

    @property
    def target(self) -> 'ot.GitObject':
        if self.__attached_to is None:
            target_hash = self.note_name
            repo = self.repository
            self.__attached_to = repo.get_object(target_hash)
        return self.__attached_to

    @property
    def text(self) -> str:
        return self.name[10:]