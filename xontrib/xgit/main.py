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
from pathlib import Path
from typing import MutableMapping, Any, cast
from collections.abc import Callable
import sys

from xonsh.built_ins import XonshSession
from xonsh.events import events
from xonsh.tools import chdir
from xonsh.execer import Execer

from xontrib.xgit.decorators import (
    _exports,
    _export,
    _unload_actions,
    _do_unload_actions,
    _aliases,
)
from xontrib.xgit.context import (
    _git_context,
)
from xontrib.xgit.display import (
    _xgit_on_predisplay,
    _xgit_on_postdisplay,
    _on_precommand,
)
from xontrib.xgit.vars import (
    XGIT,
    xgit_version,
)
from xontrib.xgit.display import (
    _xonsh_displayhook,
    _xgit_displayhook,
)
from xontrib.xgit.proxy import target, ProxyMetadata

@events.on_chdir
def update_git_context(olddir, newdir):
    """
    Update the git context when changing directories.
    """
    if not XGIT:
        # Not set at all so start from scratch
        target(XGIT, _git_context())
        return
    newpath = Path(newdir)
    if XGIT.worktree == newpath:
        # Going back to the worktree root
        XGIT.path = Path(".")
    if XGIT.worktree.path not in newpath.parents:
        # Not in the current worktree, so recompute the context.
        target(XGIT, _git_context())
    else:
        # Fast move within the same worktree.
        XGIT.path = Path(newdir).resolve().relative_to(XGIT.worktree.path)

# Export the functions and values we want to make available.

_export(None, "+")
_export(None, "++")
_export(None, "+++")
_export(None, "-")
_export(None, "__")
_export(None, "___")
_export("_xgit_counter")


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
    from xontrib import xgit
    ProxyMetadata.load()
    env =  xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is not a MutableMapping: {env!r}"
    env["XGIT_TRACE_LOAD"] = env.get("XGIT_TRACE_LOAD", False)
    def set_unload(
        ns: MutableMapping[str, Any],
        name: str,
        value=None,
    ):
        old_value = None
        if name in ns:
            old_value = ns[name]

            def restore_item():
                ns[name] = old_value

            _unload_actions.append(restore_item)
        else:

            def del_item():
                with suppress(KeyError):
                    del ns[name]

            _unload_actions.append(del_item)

    for name, value in _exports.items():
        set_unload(xsh.ctx, name, value)
    for name, value in _aliases.items():
        aliases = xsh.aliases
        assert aliases is not None, "XSH.aliases is None"
        set_unload(aliases, name, value)
        aliases[name] = value

    # Assertions are to flag bad test
    env = xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is a MutableMapping {env!r}"

    ctx: MutableMapping[str, Any] = xsh.ctx
    assert isinstance(ctx, MutableMapping),\
        f"XSH.ctx is not a MutableMapping: {ctx!r}"

    # Set the initial context on loading.
    target(XGIT, None)
    #_export("XGIT")
    if "_XGIT_RETURN" in xsh.ctx:
        del env["_XGIT_RETURN"]

    # Install our displayhook
    global _xonsh_displayhook
    hook = _xonsh_displayhook
    #target(XSH, xsh)

    ctx['-']  = None
    def unhook_display():
        sys.displayhook = hook

    _unload_actions.append(unhook_display)
    _xonsh_displayhook = hook
    sys.displayhook = _xgit_displayhook

    prompt_fields = env['PROMPT_FIELDS']
    assert isinstance(prompt_fields, MutableMapping), \
        f"PROMPT_FIELDS not a MutableMapping: {prompt_fields!r}"
    prompt_fields['xgit.version'] = xgit_version

    if "XGIT_ENABLE_NOTEBOOK_HISTORY" not in env:
        env["XGIT_ENABLE_NOTEBOOK_HISTORY"] = True

    if env.get("XGIT_TRACE_LOAD"):
        print("Loaded xontrib-xgit", file=sys.stderr)
    target(XGIT, _git_context())
    return _exports


def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """Clean up on unload."""
    env = xsh.env
    assert isinstance(env, MutableMapping),\
        f"XSH.env is not a MutableMapping: {env!r}"

    if env.get("XGIT_TRACE_LOAD"):
        print("Unloading xontrib-xgit", file=sys.stderr)
    _do_unload_actions()

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
    remove("on_chdir", update_git_context)
    remove("xgit_on_predisplay", _xgit_on_predisplay)
    remove("xgit_on_postdisplay", _xgit_on_postdisplay)
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
    ProxyMetadata.unload()
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