"""
This is a file of utilities initially targeting exploration of git repositories.

It provides the following commands:
- git-cd: Change the current working directory to the path provided.
- git-pwd: Print the current working directory and git context information if available.
- git-ls: List the contents of the current directory or the directory provided.

In addition, it extends the displayhook to provide the following variables:
- _: The last value displayed.
- __: The value displayed before the last one.
- ___: The value displayed before the one before the last one.
- _<m>" The nth value.
"""

from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import MutableMapping, Any, cast
from collections.abc import Callable
import sys

from xonsh.built_ins import XonshSession
from xonsh.events import events
from xonsh.execer import Execer

from xontrib.xgit.decorators import (
    _exports,
    _export,
    session,
)
from xontrib.xgit.display import (
    _on_xgit_predisplay,
    _on_xgit_postdisplay,
    _on_precommand,
    _xonsh_displayhook,
    _xgit_displayhook,
)
import xontrib.xgit.context as ct
from xontrib.xgit.types import GitDirNotFoundError, GitException

# Export the functions and values we want to make available.

_export(None, "+")
_export(None, "++")
_export(None, "+++")
_export(None, "-")
_export(None, "__")
_export(None, "___")
_export("_xgit_counter")

_xgit_version: str = ""
def xgit_version():
    """
    Return the version of xgit.
    """
    global _xgit_version
    if _xgit_version:
        return _xgit_version
    from importlib.metadata import version
    _xgit_version = version("xontrib-xgit")
    return _xgit_version

events.doc('on_xgit_load', 'Runs when the xgit xontrib is loaded.')
events.doc('on_xgit_unload', 'Runs when the xgit xontrib is unloaded.')

def _load_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """
    this function will be called when loading/reloading the xontrib.

    Args:
        xsh: the current xonsh session instance, serves as the interface to
            manipulate the session.
            This allows you to register new aliases, history backends,
            event listeners ...
        **kwargs: it is empty as of now. Kept for future proofing.
    Returns:
        dict: this will get loaded into the current execution context
    """

    env =  xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is not a MutableMapping: {env!r}"
    # Set the context on loading.
    env["XGIT_TRACE_LOAD"] = env.get("XGIT_TRACE_LOAD", False)
    @events.on_chdir
    @session()
    def update_git_context(olddir, newdir,
                           XSH: XonshSession,
                           XGIT,
                           stderr=sys.stderr,
                           **_):
        """
        Update the git context when changing directories.
        """

        newpath = Path(newdir)
        path = newpath
        try:
            while path != path.parent:
                if path.suffix == ".git" or path.name == ".git":
                    XGIT.open_repository(path)
                    return
                if (path / ".git").exists():
                    XGIT.open_worktree(path)
                    return
        except Exception as ex:
            raise GitException(F"Failed to open worktree at {newpath}") from ex

    # Assertions are to flag bad test
    env = xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is a MutableMapping {env!r}"

    ctx: MutableMapping[str, Any] = xsh.ctx
    assert isinstance(ctx, MutableMapping),\
        f"XSH.ctx is not a MutableMapping: {ctx!r}"

    if "_XGIT_RETURN" in xsh.ctx:
        del env["_XGIT_RETURN"]

    # Install our displayhook
    global _xonsh_displayhook
    hook = _xonsh_displayhook

    ctx['-']  = None
    def unhook_display(**_):
        sys.displayhook = hook

    _xonsh_displayhook = hook
    events.on_xgit_unload(unhook_display)
    sys.displayhook = _xgit_displayhook


    prompt_fields = env['PROMPT_FIELDS']
    assert isinstance(prompt_fields, MutableMapping), \
        f"PROMPT_FIELDS not a MutableMapping: {prompt_fields!r}"
    prompt_fields['xgit.version'] = xgit_version

    if "XGIT_ENABLE_NOTEBOOK_HISTORY" not in env:
        env["XGIT_ENABLE_NOTEBOOK_HISTORY"] = True

    XGIT = ct._GitContext(xsh)
    env['XGIT'] = XGIT
    events.on_xgit_load.fire(
        XSH=xsh,
        XGIT=XGIT,
    )
    with suppress(GitDirNotFoundError):
        XGIT.open_repository(Path.cwd())

    if env.get("XGIT_TRACE_LOAD"):
        print("Load ed xontrib-xgit", file=sys.stderr)
    return _exports


def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """Clean up on unload."""
    env = xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is not a MutableMapping: {env!r}"

    if env.get("XGIT_TRACE_LOAD"):
        print("Unloading xontrib-xgit", file=sys.stderr)

    if "_XGIT_RETURN" in xsh.ctx:
        del xsh.ctx["_XGIT_RETURN"]

    sys.displayhook = _xonsh_displayhook

    def remove(event: str, func: Callable):
        try:
            getattr(events, event).remove(func)
        except ValueError:
            pass
        except KeyError:
            pass

    remove("on_precommand", _on_precommand)
    remove("on_xgit_predisplay", _on_xgit_predisplay)
    remove("on_xgit_postdisplay", _on_xgit_postdisplay)
    env = xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is not a MutableMapping: {env!r}"
    prompt_fields = env['PROMPT_FIELDS']
    assert isinstance(prompt_fields, MutableMapping),\
        "PROMPT_FIELDS not a MutableMapping"

    if env.get("XGIT_TRACE_LOAD"):
        print("Unloaded xontrib-xgit", file=sys.stderr)
    if 'xgit.version' in prompt_fields:
        del prompt_fields['xgit.version']

    for m in [m for m in sys.modules if m.startswith("xontrib.xgit.")]:
        del sys.modules[m]
    return dict()

if __name__ == "__main__" and False:
    print("This is a xontrib module for xonsh, it is not meant to be executed.")
    print("But we'll do it anyway.")

    from xonsh.built_ins import XSH as _XSH
    #_XSH.env={}
    _XSH.load(execer=Execer())
    _load_xontrib_(_XSH)
    for arg in sys.argv[1:]:
        print(f"Executing {arg}")
        execer = _XSH.execer
        assert execer is not None, "No execer"
        execer.exec(arg)
    _unload_xontrib_(_XSH)