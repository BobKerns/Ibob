'''
Utilities for running git commands.
'''

from typing import Sequence, MutableMapping, Generator, cast, Any
import sys

from xonsh.procs.pipelines import HiddenCommandPipeline
from xontrib.xgit import vars as xv


def _run_stdout(cmd: Sequence[str]) -> str:
    """
    Run a command and return the standard output.
    """
    env = xv.XSH.env
    assert isinstance(env, MutableMapping), "env() not a mapping"

    if env.get("XGIT_TRACE_COMMANDS"):
        cmdline = " ".join(cmd)
        print(f"Running {cmdline}", file=sys.stderr)
    return cast(str, xv.XSH.subproc_captured_stdout([*cmd, ("2>", "/dev/null")]))

def _run_object(cmd: Sequence[str]) -> HiddenCommandPipeline:
    env = xv.XSH.env
    assert isinstance(env, MutableMapping), "env() not a mapping"

    if env.get("XGIT_TRACE_COMMANDS"):
        cmdline = " ".join(cmd)
        print(f'Running {cmdline}', file=sys.stderr)
    result = xv.XSH.subproc_captured_object(
        [*cmd, ("2>", "/dev/null")])
    if not isinstance(result, HiddenCommandPipeline):
        cmdline = " ".join(cmd)
        raise RuntimeError(f"Failed to run {cmdline}")
    return result

def _run_lines(cmd: Sequence[str]) -> Generator[str, Any, None]:
    """
    Run a command and return the standard output as a str iterator.

    Throws an exception if the command fails.
    """
    return _run_object(cmd).itercheck()


def _run_binary(cmd: Sequence[str]):
    """
    Run a command and return the standard output as bytes.

    Throws an exception if the command fails.
    """
    return _run_object(cmd).stdout.raw


def _run_text(cmd: Sequence[str]):
    """
    Run a command and return the standard output as text.

    Throws an exception if the command fails.
    """
    return _run_object(cmd).stdout.text


def _run_stream(cmd: Sequence[str]):
    """
    Run a command and return the standard output as stream.

    Throws an exception if the command fails.
    """
    return _run_object(cmd).stdout
