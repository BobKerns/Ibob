'''
A mixin class for git commands on a repository or worktree.
'''

from abc import abstractmethod
from pathlib import Path
from subprocess import (
    run, PIPE, Popen, CompletedProcess,
)
import shutil
from typing import (
    Optional, runtime_checkable, Protocol,
    IO, cast,
    TYPE_CHECKING,
)
from collections.abc import Sequence, Iterator

from xontrib.xgit.types import ObjectId, CommitId, GitException

if TYPE_CHECKING:
    import xontrib.xgit.context_types as ct

@runtime_checkable
class GitCmd(Protocol):
    '''
    Context for git commands.
    '''
    @abstractmethod
    def run(self, cmd: str|Path, *args,
            cwd: Optional[Path]=None,
            **kwargs) -> CompletedProcess:
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
    def run_list(self, cmd: str|Path, *args,
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
    def run_lines(self, *args,
                   cwd: Optional[Path]=None,
                   **kwargs) -> Iterator[str]:
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
    def run_stream(self, cmd: str|Path, *args,
                   cwd: Optional[Path]=None,
                   **kwargs) -> IO[str]:
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
    def git_string(self, subcmd: str, *args, **kwargs) -> str:
        '''
        Run a git command and return the output as a string.

        PARAMETERS
        ----------
        subcmd: str
            The git subcommand to run.
        args: Any
            The arguments to the command.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.
        '''
        ...

    @abstractmethod
    def git_list(self, subcmd: str, *args, **kwargs) -> list[str]:
        '''
        Run a git command and return the output as a list of lines.

        PARAMETERS
        ----------
        subcmd: str
            The git subcommand to run.
        args: Any
            The arguments to the command.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.

        RETURNS
        -------
        list[str]
            The output of the command.
        '''
        ...

    @abstractmethod
    def git_lines(self, subcmd: str, *args, **kwargs) -> Iterator[str]:
        '''
        Run a git command and return the output as an iterator of lines.

        PARAMETERS
        ----------
        subcmd: str
            The git subcommand to run.
        args: Any
            The arguments to the command.
        kwargs: Any
            Additional arguments to pass to `subprocess.Popen`.

        RETURNS
        -------
        Iterator[str]
            The output of the command
        '''
        ...

    @abstractmethod
    def git_stream(self, subcmd: str, *args, **kwargs) -> IO[str]:
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

        RETURNS
        -------
        IO[str]
            The output of the command. .read() returns a str object
        '''

    @abstractmethod
    def git_binary(self, subcmd: str, *args, **kwargs) -> IO[bytes]:
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

        RETURNS
        -------
        IO[bytes]
            The output of the command. .read() returns a bytes object.
        '''

    @abstractmethod
    def rev_parse(self, param: str, /) -> ObjectId:
        '''
        Use `git rev-parse` to get a single parameter.

        PARAMETERS
        ----------
        param: str
            The parameter to get.

        RETURNS
        -------
        str

        '''
        ...

    @abstractmethod
    def rev_parse_n(self, /, *params: str) -> Sequence[str] | str:
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
    def worktree_locations(self, path: Path) -> tuple[Path, Path, Path, ObjectId]:
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

    def symbolic_ref(self, ref: str) -> str:
        '''
        Get the target of a symbolic reference.

        PARAMETERS
        ----------
        ref: str
            The reference to get the target of.

        RETURNS
        -------
        str
            The target of the symbolic reference.
            This is usually a branch or tag name,
            but can be a commit id.
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

    def run_lines(self, cmd: str|Path, *args,
                cwd: Optional[Path]=None,
                stdout=PIPE,
                text: bool=True,
                check: bool=True,
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
        if code := proc.returncode:
            raise GitException(f"Command failed: {cmd} {args} {code}")

    def run_stream(self, cmd: str|Path, *args,
                cwd: Optional[Path]=None,
                stdout=PIPE,
                text: bool=False,
                **kwargs) :
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
            text=True,
            cwd=self.__get_path(cwd),
            **kwargs)
        stream = proc.stdout
        if stream is None:
            raise ValueError("No stream")
        return stream


    def run_binary(self, cmd: str|Path, *args,
                cwd: Optional[Path]=None,
                stdout=PIPE,
                text: bool=False,
                **kwargs)  -> IO[bytes]:
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
        return cast(IO[bytes], stream)

    def run_string(self, cmd: str|Path, *args,
                   **kwargs) -> str:
        return self.run(cmd, *args, **kwargs).stdout.strip()

    def run_list(self, cmd: str|Path, *args,
                    **kwargs) -> list[str]:
        return list(self.run_lines(cmd, *args, **kwargs))

    def git_string(self, subcmd: str, *args,
            stdout=PIPE,
            text: bool=True,
            check: bool=True,
            **kwargs) -> str:
        return self.run_string(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            check=check,
            **kwargs)

    def git_list(self, subcmd: str, *args,
            stdout=PIPE,
            text: bool=True,
            check: bool=True,
            **kwargs) -> list[str]:
        return self.run_list(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            check=check,
            **kwargs)

    def git_lines(self, subcmd: str, *args,
                **kwargs):
        return self.run_lines(str(self.__git), subcmd, *args,
                            **kwargs)

    def git_stream(self, subcmd: str, *args,
                stdout=PIPE,
                text: bool=False,
                **kwargs):
        return self.run_stream(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            **kwargs)

    def git_binary(self, subcmd: str, *args,
                stdout=PIPE,
                text: bool=False,
                **kwargs) -> IO[bytes]:
        return self.run_binary(str(self.__git), subcmd, *args,
            stdout=stdout,
            text=text,
            **kwargs)

    def rev_parse(self, param: str, /) -> CommitId:
        return CommitId(ObjectId(self.rev_parse_n(param)[0]))

    def rev_parse_n(self, /, *params: str) -> Sequence[str]:
        """
        Use `git rev-parse` to get multiple parameters at once.
        """
        val = self.git_list("rev-parse", *params)
        if val:
            result = val
        else:
            # Try running them individually.
            result = [self.git_string("rev-parse", param) for param in params]
        return result


    def worktree_locations(self, path: Path) -> tuple[Path, Path, Path, CommitId]:
        path = path.resolve()
        for p in (path, *path.parents):
            git_dir = p / ".git"
            if git_dir.is_dir():
                commit = self.rev_parse("HEAD")
                return path, path, git_dir, commit
            git_file = path / ".git"

            if git_file.is_file():
                worktree, private, common, commit = self.rev_parse_n(
                    "--show-toplevel",
                    "--absolute-git-path",
                    "--git-common-dir", "HEAD"
                )
                return (
                    Path(worktree),
                    Path(private),
                    Path(common),
                    CommitId(ObjectId(commit))
                )
        raise GitException(f"   Not a git repository: {path}")


    def symbolic_ref(self, ref: str) -> str:
        '''
        Get the target of a symbolic reference.

        PARAMETERS
        ----------
        ref: str
            The reference to get the target of.

        RETURNS
        -------
        str
            The target of the symbolic reference.
            This is usually a branch or tag name,
            but can be a commit id.
        '''
        return self.git_string("symbolic-ref", '--quiet', ref,
                               check=False)
