'''
Miscellaneous utility functions.
'''

from typing import MutableMapping, TypeVar
from collections.abc import Iterable
from pathlib import Path
import sys

from xonsh.built_ins import XonshSession


def path_and_parents(path: Path):
    """
    Return the path and all of its parent directories.
    """
    yield path
    yield from path.parents


T = TypeVar('T')
def pre(v0: T, vx:  Iterable[T]) -> Iterable[T]:
    """
    Prepend an element to an iterable.
    """
    yield v0
    yield from vx


def post(vx:  Iterable[T], vn: T) -> Iterable[T]:
    """
    Append an element to an iterable.
    """
    yield from vx
    yield vn


def prepost(v0: T, vx:  Iterable[T], vn: T) -> Iterable[T]:
    """
    Prepend and append an element to an iterable.
    """
    yield v0
    yield from vx
    yield vn


def print_if(var: str, XSH: XonshSession):
    '''
    Returns a print function that is enabled if the variable `var` is in the
    environment. If the variable does not begin with `XGIT_`, then it is
    prefixed with `XGIT_SHOW_`.

    The variable is checked once on each call of this function and used
    to determine if the returned print function should be enabled or
    disabled.

    Output (if any) is to `sys.stderr`. Messages will be prefixed with
    the `var` without `XGIT_SHOW_`.

    PARAMETERS
    ----------
    var: str
        The name of the environment variable to check.
    XSH: XonshSession
        The xonsh session.
    RETURNS
    -------
    print: function
        A function that prints if the variable is in the environment.
    '''
    if not var.startswith('XGIT_'):
        var = f'XGIT_SHOW_{var}'
    env = XSH.env
    if not isinstance(env, MutableMapping):
        raise ValueError('XSH.env is not a MutableMapping')
    enable = env.get(var, False)
    def _print(*args):
        if enable:
            print(*args, file=sys.stderr)
    return _print


def shorten_branch(branch):
    '''
    Shorten a branch name for display.
    '''
    branch = str(branch)
    branch = branch.replace('refs/heads/', '')
    branch = branch.replace('refs/remotes/', '')
    branch = branch.replace('refs/tags/', 'tag:')
    return branch


def relative_to_home(path: Path) -> Path:
    """
    Get a path for display relative to the home directory.
    This is for display only.
    """
    home = Path.home()
    if path == home:
        return Path("~")
    if path == home.parent:
        return Path(f"~{home.name}")
    try:
        return Path("~") / path.relative_to(home)
    except ValueError:
        return path
