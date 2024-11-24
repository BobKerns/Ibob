'''
A mixin class for git commands on a repository or worktree.
'''

from abc import abstractmethod
from calendar import c
from pathlib import Path
from subprocess import run, PIPE, Popen
import shutil
from typing import (
    Optional, Sequence, overload, runtime_checkable, Protocol, Iterator,
)
from io import IOBase

from xontrib.xgit.types import GitHash, GitException
import xontrib.xgit.context_types as ct

@runtime_checkable
class GitCmd(Protocol):
    '''
    Context for git commands.
    '''
    @abstractmethod
    def run(self, cmd: str|Path, *args,
            cwd: Optional[Path]=None,
            **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        args: Any
            The arguments to the command.
        cwd: Optional[Path]
            The directory to run the command in, relative to this context.
        kwargs: Any
            Additional arguments to pass to `subprocess.run`.

        RETURNS
        -------
        CompletedProcess
        '''
        ...

    @abstractmethod
    def run_string(self, cmd: str|Path,
                *args,
                cwd: Optional[Path]=None,
                **kwargs) -> str:
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        cwd: Optional[Path]:
            The directory to run the command in, relative to this context.
        args: Any

        RETURNS
        -------
        str
            The output of the command.
        '''
        ...

    @abstractmethod
    def run_lines(self, cmd: str|Path, *args,
                  cwd: Optional[Path]=None,
                  **kwargs) -> list[str]:
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        args: Any
            The arguments to the command.
        cwd: Optional[Path]:
            The directory to run the command in, relative to this context.
        kwargs: Any
            Additional arguments to pass to `subprocess.run`.

        RETURNS
        -------
        list[str]
            The output of the command.
        '''
        ...

    @abstractmethod
    def run_stream(self, *args,
                   cwd: Optional[Path]=None,
                   **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        RETURNS
        -------
        Iterator[str]
            The output of the command.
        '''
        ...

    @abstractmethod
    def run_binary(self, cmd: str|Path, *args,
                   cwd: Optional[Path]=None,
                   **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        args: Any
            The arguments to the command.
        cwd: Optional[Path]:
            The directory to run the command in, relative to this context.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.

        RETURNS
        -------
        bytes
            The output of the command.
        '''
        ...

    @abstractmethod
    def git(self, subcmd: str, *args, **kwargs) -> str: ...
    @abstractmethod
    def git_lines(self, subcmd: str, *args, **kwargs) -> list[str]: ...
    @abstractmethod
    def git_stream(self, subcmd: str, *args, **kwargs) -> Iterator[str]: ...
    @abstractmethod
    def git_binary(self, subcmd: str, *args, **kwargs) -> IOBase:
        '''
        Run a git command and return the output as a binary stream.

        PARAMETERS
        ----------
        subcmd: str
            The git subcommand to run.
        args: Any
            The arguments to the command.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.
        '''

    @overload
    def rev_parse(self, params: str, /) -> str: ...
    @overload
    def rev_parse(self,param: str, *_params: str) -> Sequence[str]: ...
    @abstractmethod
    def rev_parse(self, param: str, *params: str) -> Sequence[str] | str:
        '''
        Use `git rev-parse` to get multiple parameters at once.

        PARAMETERS
        ----------
        param: str
            The parameter to get.
        params: str
            Additional parameters to get.

        RETURNS
        -------
        Sequence[str] | str
            The output of the command, one string for eah parameter.
        '''
        ...

    @abstractmethod
    def worktree_locations(self, path: Path) -> tuple[Path, Path, Path, GitHash]:
        '''
        Get location info about worktree paths:

        RETURNS
        -------
        - The root of the worktree.
        - The worktree private repository area
        - the repository's path.
        - The current commit.
        '''
        ...

class _GitCmd:
    """
    A context for a git command.
    """
    __path: Path|None
    __git: Path
    '''
    The path to the git command.
    '''
    __context: 'ct.GitContext'
    @property
    def context(self) -> 'ct.GitContext':
        return self.__context

    def __get_path(self, path: Path|str|None) -> Path:
        '''
        Get the working directory path for the command.
        '''
        if path is None:
            path = self.__path or Path.cwd()
        else:
            s_path = self.__path or Path.cwd()
            path = s_path / path
        return path.resolve()

    def __init__(self, path: Optional[Path]=None):
        if path is not None:
            path = path.resolve()
        self.__path = path
        git = shutil.which("git")
        if git is None:
            raise ValueError("git command not found")
        self.__git = Path(git)

    def run(self, cmd: str|Path, *args,
            cwd: Optional[Path]=None,
            stdout=PIPE,
            text: bool=True,
            check: bool=True,
            **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        RETURNS
        -------
        CompletedProcess
        '''
        return run([cmd, *(str(a) for a in args)],
                    cwd=self.__get_path(cwd),
                    stdout=stdout,
                    text=text,
                    check=check,
                    **kwargs)

    def run_stream(self, cmd: str|Path, *args,
                cwd: Optional[Path]=None,
                stdout=PIPE,
                text: bool=True,
                **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        args: Any
            The arguments to the command.
        cwd: Optional[Path]
            The directory to run the command in, relative to this context.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.

        RETURNS
        -------
        Iterator[str]
            The output of the command.
        '''
        proc = Popen([cmd, *(str(a) for a in args)],
            stdout=stdout,
            text=text,
            cwd=self.__get_path(cwd),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        for line in stream:
            yield line.rstrip()
        proc.wait()

    def run_binary(self, cmd: str|Path, *args,
                cwd: Optional[Path]=None,
                stdout=PIPE,
                text: bool=False,
                **kwargs):
        '''
        Run a command in the git worktree, repository, or current directory,
        depending on which subclass this is run from.

        PARAMETERS
        ----------
        cmd: str|Path
            The command to run.
        args: Any
            The arguments to the command.
        cwd: Optional[Path]:
            The directory to run the command in, relative to this context.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.

        RETURNS
        -------
        bytes

        '''
        proc = Popen([cmd, *(str(a) for a in args)],
            stdout=PIPE,
            text=False,
            cwd=self.__get_path(cwd),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        return stream

    def run_string(self, cmd: str|Path, *args,
                   **kwargs) -> str:
        return self.run(cmd, *args, **kwargs).stdout.strip()

    def run_lines(self, cmd: str|Path, *args,
                    **kwargs) -> list[str]:
        return self.run_string(cmd, *args, **kwargs).splitlines()

    def git(self, subcmd: str, *args,
            path: Optional[str|Path]=None,
            stdout=PIPE,
            text: bool=True,
            check: bool=True,
            **kwargs) -> str:
        return self.run(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            check=check,
            **kwargs).stdout.strip()

    def git_lines(self, subcmd: str, *args,
            path: Optional[str|Path]=None,
            stdout=PIPE,
            text: bool=True,
            check: bool=True,
            **kwargs) -> list[str]:
        return self.run(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            check=check,
            **kwargs).stdout.splitlines()

    def git_stream(self, subcmd: str, *args,
                path: Optional[str|Path]=None,
                **kwargs):
        return self.run_stream(str(self.__git), subcmd, *args,
            **kwargs)

    def git_binary(self, subcmd: str, *args,
                cwd: Optional[str|Path]=None,
                stdout=PIPE,
                text: bool=False,
                **kwargs):

        proc = Popen([str(self.__git), subcmd, *args],
            stdout=stdout,
            text=text,
            cwd=self.__get_path(cwd),
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
            result = val
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

    def worktree_locations(self, path: Path) -> tuple[Path, Path, Path, GitHash]:
        path = path.resolve()
        for p in path.parents:
            git_dir = path / ".git"
            if git_dir.is_dir():
                commit = self.rev_parse("HEAD")
                return path, path, git_dir, commit
            git_file = path / ".git"

            if git_file.is_file():
                worktree, private, common, commit = self.rev_parse(
                    "--show-toplevel",
                    "--absolute-git-path",
                    "--git-common-dir", "HEAD"
                )
                return Path(worktree), Path(private), Path(common), commit
        raise GitException(f"   Not a git repository: {path}")