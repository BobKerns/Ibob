'''
Utilities for running git commands.
'''

from typing import Sequence
import io
import sys

from xonsh.built_ins import XSH


def _run_stdout(cmd: Sequence[str]) -> str:
    """
    Run a command and return the standard output.
    """
    if XSH.env.get("XGIT_TRACE_COMMANDS"):
        cmdline = " ".join(cmd)
        print(f"Running {cmdline}", file=sys.stderr)
    return XSH.subproc_captured_stdout([*cmd, ("2>", "/dev/null")])


def _run_object(cmd: Sequence[str]) -> io.StringIO:
    """
    Run a command and return the standard output as an iterator.

    Throws an exception if the command fails.
    """
    if XSH.env.get("XGIT_TRACE_COMMANDS"):
        cmdline = " ".join(cmd)
        print(f'Running {cmdline}', file=sys.stderr)
    return XSH.subproc_captured_object([*cmd, ("2>", "/dev/null")]).itercheck()

