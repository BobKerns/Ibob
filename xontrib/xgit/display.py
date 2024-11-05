"""
Modify the displayhook to handle value-returning commands and update history variables.
This gives a notebook-style history of the last three values displayed, and
allows display of python values returned from commands.
"""

from typing import Any
import sys

from xonsh.procs.pipelines import HiddenCommandPipeline
from xonsh.events import events
import builtins

from xontrib.xgit.vars import (
    _xgit_count,
    XSH,
    XGitProxy,
)

# Our events:

events.doc(
    "xgit_on_predisplay",
    "Runs before displaying the result of a command with the value to be displayed.",
)
events.doc(
    "xgit_on_postdisplay",
    "Runs after displaying the result of a command with the value displayed.",
)


_xonsh_displayhook = sys.displayhook
"""
Xonsh's original displayhook.
"""

def _xgit_displayhook(value: Any):
    """
    Add handling for value-returning commands, pre- and post-display events,
    and exception protection.
    """
    ovalue = value
    env = XSH.env
    assert isinstance(env, dict), "env() not a mapping"
    if isinstance(value, HiddenCommandPipeline):
        value = XSH.ctx.get("_XGIT_RETURN", value)
        if "_XGIT_RETURN" in XSH.ctx:
            if env.get("XGIT_TRACE_DISPLAY"):
                print("clearing _XGIT_RETURN in XSH.ctx", file=sys.stderr)
            del XSH.ctx["_XGIT_RETURN"]
        else:
            if env.get("XGIT_TRACE_DISPLAY"):
                msg = (
                    "No _XGIT_RETURN, "
                    + "result has been displayed with str() and suppressed"
                )
                print(msg, file=sys.stderr)
    if isinstance(value, XGitProxy):
        value = value._target

    if env.get("XGIT_TRACE_DISPLAY") and ovalue is not value:
        sys.stdout.flush()
        print(
            f"DISPLAY: {ovalue=!r} {value=!r} type={type(ovalue).__name__}", sys.stderr
        )
        sys.stderr.flush()
    try:
        events.xgit_on_predisplay.fire(value=value)
        sys.stdout.flush()
        _xonsh_displayhook(value)
        events.xgit_on_postdisplay.fire(value=value)
    except Exception as ex:
        print(ex, file=sys.stderr)
        sys.stderr.flush()


@events.xgit_on_predisplay
def _xgit_on_predisplay(value: Any):
    """
    Update the notebook-style convenience history variables before displaying a value.
    """
    global count
    env = XSH.env
    assert isinstance(env, dict), "env() not a mapping"
    if (
        value is not None
        and not isinstance(value, HiddenCommandPipeline)
        and env.get("XGIT_ENABLE_NOTEBOOK_HISTORY")
    ):
        count = _xgit_count()
        ivar = f"_i{count}"
        ovar = f"_{count}"
        XSH.ctx[ivar] = XSH.ctx["-"]
        XSH.ctx[ovar] = value
        print(f"{ovar}: ", end="")


@events.xgit_on_postdisplay
def _xgit_on_postdisplay(value: Any):
    """
    Update _, __, and ___ after displaying a value.
    """
    if value is not None and not isinstance(value, HiddenCommandPipeline):
        setattr(builtins, ",", value)
        XSH.ctx["__"] = XSH.ctx["+"]
        XSH.ctx["___"] = XSH.ctx["++"]


@events.on_precommand
def _on_precommand(cmd: str):
    """
    Before running a command, save our temporary variables.
    We associate them with the session rather than the module.
    These names are deliberately impossible to use, and are named
    after similar variables long used in REPLs.

    _, __, and ___ are the last three values displayed, and are
    directly useful. The variables here are simply to facilitate
    updating those values.
    """
    env = XSH.env
    assert isinstance(env, dict), "env() not a mapping"
    if "_XGIT_RETURN" in XSH.ctx:
        if env.get("XGIT_TRACE_DISPLAY"):
            print("Clearing _XGIT_RETURN before command", file=sys.stderr)
        del XSH.ctx["_XGIT_RETURN"]
    XSH.ctx["-"] = cmd.strip()
    XSH.ctx["+"] = builtins._  # type: ignore # noqa
    XSH.ctx["++"] = XSH.ctx.get("__")
    XSH.ctx["+++"] = XSH.ctx.get("___")

