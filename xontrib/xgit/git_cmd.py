'''
A mixin class for git commands on a repository or worktree.
'''

import sys
from abc import abstractmethod
from pathlib import Path
from subprocess import run, PIPE, Popen
import shutil
from typing import (
    Optional, Sequence, overload, runtime_checkable, Protocol, Iterator,
)
from io import IOBase

@runtime_checkable
class GitCmd(Protocol):
    '''
    Context for git commands.
    '''
    @abstractmethod
    def git(self, *args, **kwargs) -> str: ...
    @abstractmethod
    def git_lines(self, *args, **kwargs) -> list[str]: ...
    @abstractmethod
    def git_stream(self, *args, **kwargs) -> Iterator[str]: ...
    @abstractmethod
    def git_binary(self, *args, **kwargs) -> IOBase: ...

    @overload
    def rev_parse(self, params: str, /) -> str: ...
    @overload
    def rev_parse(self,param: str, *_params: str) -> Sequence[str]: ...
    @abstractmethod
    def rev_parse(self, param: str, *params: str) -> Sequence[str] | str: ...


class _GitCmd:
    """
    A context for a git command.
    """
    __path: Path
    __git: Path
    def __get_path(self, path: Path|str|None) -> Path:
        if path is None:
            return self.__path
        return (self.__path / path).resolve()
    def __init__(self, path: Path):
        self.__path = path.resolve()
        git = shutil.which("git")
        if git is None:
            raise ValueError("git command not found")
        self.__git = Path(git)
    def run(self, *args, **kwargs):
         return  run(args, **kwargs)
    def git(self, *args,
            path: Optional[str|Path]=None,
            check=True,
            **kwargs) -> str:
        return self.run(str(self.__git), *args,
            stdout=PIPE,
            text=True,
            check=check,
            cwd=self.__get_path(path),
            **kwargs).stdout.strip()
    def git_lines(self, *args,
            path: Optional[str|Path]=None,
            check=True,
            **kwargs) -> list[str]:
        return self.run(str(self.__git),*args,
            stdout=PIPE,
            text=True,
            check=check,
            cwd=self.__get_path(path),
            **kwargs).stdout.splitlines()
    def git_stream(self, *args,
                path: Optional[str|Path]=None,
                **kwargs):
        cmd = [str(a) for a in (self.__git, *args)]
        proc = Popen(cmd,
            stdout=PIPE,
            text=True,
            cwd=self.__get_path(path),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        for line in stream:
            yield line.rstrip()
        proc.wait()

    def git_binary(self, *args,
                   path: Optional[str|Path]=None,
                     **kwargs):

        cmd = [str(a) for a in (self.__git, *args)]
        proc = Popen(cmd,
            stdout=PIPE,
            text=False,
            cwd=self.__get_path(path),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        return stream

    @overload
    def rev_parse(self, params: str, /) -> str: ...
    @overload
    def rev_parse(self,param: str, *_params: str) -> Sequence[str]: ...
    def rev_parse(self, param: str, *params: str) -> Sequence[str] | str:
        """
        Use `git rev-parse` to get multiple parameters at once.
        """
        all_params = [param, *params]
        val = self.git_lines("rev-parse", *all_params)
        if val:
            return val
        else:
            # Try running them individually.
            result = [self.git("rev-parse", param) for param in all_params]
        if len(all_params) == 1:
            # Otherwise we have to assign like `value, = multi_params(...)`
            # The comma is` necessary to unpack the single value
            # but is confusing and easy to forget
            # (or not understand if you don't know the syntax).
            return result[0]
        return result
