'''
This manages type conversions for xgit, mostly from
`str` to the declared types.
'''

from pathlib import Path, PurePosixPath
from typing import Any, TypeAliasType, cast
import re

from xontrib.xgit.types import (
    ObjectId, GitEntryMode, GitObjectType, GitRepositoryId,
    GitReferenceType, GitObjectReference, JsonAtomic, JsonArray, JsonObject,
    JsonData, Directory, File, PythonFile, KeywordArity, KeywordSpec,
    KeywordSpecs, KeywordInputSpec, KeywordInputSpecs, HeadingStrategy,
    ColumnKeys,
)

# Usually a max of 40 characters for SHA-1, but can be 64 if SHA-256 is enabled.
RE_GIT_ALIAS = re.compile(r'^(?P<hash>[0-9a-f]{,64})$')
RE_GIT_REPO_ALIAS = re.compile(r'^(?:(?P<repo>[^:]+):)?(?P<hash>[0-9a-f]{,64})$')

class ConversionManager:
    '''
    Manages type conversions for xgit.
    '''
    def __init__(self):
        self._converters = {}
        self._converters[Path] = self._convert_path
        self._converters[PurePosixPath] = self._convert_pure_posix_path
        self._converters[ObjectId] = self._convert_git_hash
        self._converters[GitEntryMode] = self._convert_git_entry_mode
        self._converters[GitObjectType] = self._convert_git_object_type
        self._converters[GitRepositoryId] = self._convert_git_repository_id
        self._converters[JsonAtomic] = self._convert_json_atomic
        self._converters[JsonArray] = self._convert_json_array
        self._converters[JsonObject] = self._convert_json_object
        self._converters[JsonData] = self._convert_json_data
        self._converters[Directory] = self._convert_directory
        self._converters[File] = self._convert_file
        self._converters[PythonFile] = self._convert_python_file

    def convert(self, value: Any, type_: type|TypeAliasType) -> Any:
        '''
        Converts a value to a type.
        '''
        if type_ in self._converters:
            return self._converters[type_](value)
        return value

    def _convert_path(self, value: Any) -> Path:
        return Path(value)

    def _convert_pure_posix_path(self, value: Any) -> PurePosixPath:
        return PurePosixPath(value)


    def _convert_git_hash(self, value: Any) -> ObjectId:
        if isinstance(value, str):
            match = RE_GIT_ALIAS.match(value)
            if match:
                return ObjectId(match.group('hash'))
            match = RE_GIT_REPO_ALIAS.match(value)
            if match:
                return ObjectId(match.group('hash'))
        return ObjectId(value)

    def _convert_git_entry_mode(self, value: Any) -> GitEntryMode:
        return cast(GitEntryMode, value)

    def _convert_git_object_type(self, value: Any) -> GitObjectType:
        return cast(GitObjectType, value)

    def _convert_git_repository_id(self, value: Any) -> GitRepositoryId:
        return GitRepositoryId(value)

    def _convert_json_atomic(self, value: Any) -> JsonAtomic:
        return value

    def _convert_json_array(self, value: Any) -> JsonArray:
        return [self.convert(v, JsonData) for v in value]

    def _convert_json_object(self, value: Any) -> JsonObject:
        return {k: self.convert(v, JsonData) for k, v in value.items()}

    def _convert_json_data(self, value: Any) -> JsonData:
        if isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, list):
            return self._convert_json_array(value)
        elif isinstance(value, dict):
            return self._convert_json_object(value)
        return None

    def _convert_directory(self, value: Any) -> Directory:
        return Path(value)

    def _convert_file(self, value: Any) -> File:
        return Path(value)


    def _convert_python_file(self, value: Any) -> PythonFile:
        return Path(value)
