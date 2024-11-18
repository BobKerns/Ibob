from contextlib import contextmanager, suppress
from inspect import currentframe, stack
from pathlib import Path
from threading import RLock
from types import ModuleType as Module
import pytest
from importlib import import_module
from typing import Callable, Any, Generator, NamedTuple, Optional, TypeAlias, cast
import sys
import os

from xonsh.built_ins import XonshSession

def run_stdout(args, **kwargs):
    from subprocess import run, PIPE
    run(args, check=True, stdout=PIPE, text=True, **kwargs).stdout

def cleanup(target: dict[str, Any], before: dict[str, Any], loaded: dict[str, Any], after: dict[str, Any]):
    '''
    Undo additions and deletionis, while preserving modifications.
    '''
    all_vars = after.keys() | loaded.keys() | before.keys()
    for k in all_vars:
        if k in after and k not in loaded:
            # This is a variable that was added by the test
            pass
        elif k in after and k in loaded and (after[k] is not loaded[k]):
            # This is a variable that was modified by the test
            pass
        elif k not in after and k in loaded:
            # This is a variable that was deleted by the test
            pass
        elif k not in before and k in loaded:
            # This is a variable that was added by the fixture
            del target[k]
        elif k in before and k not in loaded:
            # This is a variable that was deleted by the fixture
            target[k] = before[k]
        elif k in before and k in loaded and (before[k] is not loaded[k]):
            # This is a variable that was modified by the fixture
            target[k] = before[k]
        else:
            # This is a variable that was not touched by either
            pass

@pytest.fixture()
def sysdisplayhook(with_events):
    """
    Fixture to capture the current sys.displayhook and restore it afterwards.
    """
    with modules_lock:
        old_displayhook = sys.displayhook
        try:
            yield
        finally:
            sys.displayhook = old_displayhook

class LoadedModules(NamedTuple):
    modules: list[Module]
    variables: dict[str, Any]

modules_lock = RLock()
@pytest.fixture()
def modules():
    """
    Fixture to load a module or modules for testing.

    This is a context manager that takes the names
    of modules to load into the local namespace, and
    then unloads them afterwards.

    Usage:

    def test_my_module(modules):
        with modules('my.module'):
            assert callable(my_function_from_my_module)

    The module, and any modules it load, will be unloaded afterwards.
    """
    with modules_lock:
        existing_outer_modules = dict(sys.modules)
        @contextmanager
        def modules(*mod_names: str):
            with modules_lock:
                top = currentframe() or stack()[0].frame
                frame = top.f_back
                assert frame is not None
                frame = frame.f_back
                assert frame is not None
                f_globals = frame.f_globals
                before_inner_modules = dict(sys.modules)
                before = dict(f_globals)
                mods = [import_module(m) for m in mod_names]
                loaded_inner_modules = dict(sys.modules)
                kwargs = {
                    k:v
                    for m in reversed(mods)
                    for k,v in m.__dict__.items()
                }
                f_globals.update(kwargs)
                loaded = dict(f_globals)
                try:
                    yield LoadedModules(modules=mods, variables=kwargs)
                finally:
                    after = dict(f_globals)
                    after_inner_modules = dict(sys.modules)
                    cleanup(f_globals, before, loaded, after)
                    cleanup(sys.modules, before_inner_modules, loaded_inner_modules, after_inner_modules)

        try:
            yield modules
        finally:
            sys.modules.clear()
            sys.modules.update(existing_outer_modules)

@pytest.fixture(autouse=True)
def debug_env(monkeypatch  ):
    monkeypatch.setenv("XGIT_TRACE_LOAD", "1")
    monkeypatch.setenv("XGIT_TRACE_DISPLAY", "1")
    monkeypatch.setenv("XGIT_TRACE_COMMANDS", "1")
    monkeypatch.setenv("XGIT_TRACE_OBJECTS", "1")
    monkeypatch.setenv("XGIT_TRACE_REFERENCES", "1")
    monkeypatch.setenv("XGIT_TRACE_CONTEXTS", "1")
    monkeypatch.setenv("XGIT_TRACE_VARS", "1")
    monkeypatch.setenv("XGIT_TRACE_PROXY", "1")
    monkeypatch.setenv("XGIT_TRACE_TARGET", "1")
    monkeypatch.setenv("XONSH_SHOW_TRACEBACK", "1")
    monkeypatch.setenv("XONSH_TRACE_SUBPROC", "1")

@pytest.fixture(autouse=True)
def clean_modules():
    """
    Ensure a clean module namespace before and after each test.
    """
    import sys
    for k in list(sys.modules.keys()):
        if k.startswith('xontrib.xgit'):
            del sys.modules[k]
    try:
        yield
    finally:
        for k in list(sys.modules.keys()):
            if k.startswith('xontrib.xgit'):
                del sys.modules[k]

Loader: TypeAlias = Callable[[XonshSession], dict[str, Any]]

class XontribModule(NamedTuple):
    XSH: XonshSession
    module: Module
    load: Loader|None
    unload: Loader|None

@contextmanager
def session_active(module, xonsh_session) -> Generator[XontribModule, None, None]:
    '''
    Context manager to load and unload a xontrib module.
    '''
    _load = None
    _unload = None
    if '_load_xontrib_' in module.__dict__:
        _load = module._load_xontrib_

    if '_unload_xontrib_' in module.__dict__:
        _unload = module._unload_xontrib_
    if _load is not None:
        _load(xonsh_session)
    yield XontribModule(
        XSH=xonsh_session,
        module=module,
        load=_load,
        unload=_unload)
    if _unload is not None:
        _unload(xonsh_session)

@pytest.fixture()
def with_xgit(xonsh_session, modules, sysdisplayhook):
    with modules('xontrib.xgit') as ((module,), kwargs):
        assert module is not None
        _load_xontrib_ = module.__dict__['_load_xontrib_']
        _unload_xontrib_ = module.__dict__['_unload_xontrib_']
        assert callable(kwargs['_load_xontrib_'])
        assert callable(kwargs['_unload_xontrib_'])
        load = cast(Loader, _load_xontrib_)
        unload = cast(Loader, _unload_xontrib_)

        def _with_xgit(t: Callable, *more_modules):
            if more_modules:
                with modules(*more_modules) as (m, more_kwargs):
                    with session_active(module, xonsh_session) as xontrib_module:
                        params = {
                            **xontrib_module._asdict(),
                            **kwargs,
                            **more_kwargs
                        }
                        return t(xontrib_module, **params)
            with session_active(module, xonsh_session) as xontrib_module:
                return t(xontrib_module, **{**xontrib_module._asdict(), **kwargs})
        yield _with_xgit

CWD_LOCK = RLock()
@pytest.fixture()
def chdir():
    '''
    Change the working directory for the duration of the test.
    Locks to prevent simultaneous changes.
    '''
    from pathlib import Path
    import os
    def chdir(path) -> Path:
        path = Path(path)
        os.chdir(path)
        return path

    with CWD_LOCK:
        old = Path.cwd()
        try:
            yield chdir
        finally:
            os.chdir(old)

@pytest.fixture()
def with_events():
    from xonsh.events import events
    existing = {
        k: set(getattr(events, k))
        for k in dir(events)
        if k.startswith('on_')
        if hasattr(getattr(events, k), '_handlers')}
    yield events
    for k, v in existing.items():
        getattr(events, k)._handlers.clear()
        getattr(events, k)._handlers.update(v)
    for k in dir(events):
        if k.startswith('on_') and hasattr(getattr(events, k), '_handlers'):
            if k not in existing:
                delattr(events, k)

@pytest.fixture()
def test_branch(modules):
    '''
    Fixture to create a test branch.
    '''
    from subprocess import run
    from secrets import token_hex
    name = f'test/{token_hex(8)}'
    with modules('xontrib.xgit.context') as ((m_ctx,), vars):
        try:
            run(['git', 'branch', name])
            m_ctx.__dict__['DEFAULT_BRANCH'] = name
            yield name
        finally:
            run(['git', 'branch', '-D', name])

@pytest.fixture()
def git():
    '''
    Fixture to run git commands.
    '''
    from subprocess import run, PIPE
    from shutil import which
    _git = which('git')
    if _git is None:
        raise ValueError("git is not installed")
    def git(*args, cwd: Optional[Path|str], **kwargs):
        if cwd is not None:
            cwd = str(cwd)
        return run([_git, *args],
                   check=True,
                   stdout=PIPE,
                   text=True,
                   env={**os.environ},
                   cwd=cwd,
                   **kwargs
                ).stdout.rstrip()
    return git

repository_lock = RLock()
@pytest.fixture()
def repository(with_xgit, git, chdir):
    '''
    Fixture to create a test repository.
    '''
    from tempfile import mkdtemp
    from secrets import token_hex
    from shutil import rmtree
    with repository_lock:
        tmpname = mkdtemp()
        old = Path.cwd()
        chdir(tmpname)
        tmp = Path.cwd()
        def _t(*_, _GitRepository, **__):
                parent = Path(tmp)
                token = token_hex(16)
                config = parent / f'.gitconfig-{token}'
                with config.open('w') as f:
                    f.write('[user]\n\temail = bogons@bogus.com\n\tname = Fake Name\n')
                repo = parent / f'test-{token}'
                file= repo / 'test.txt'
                git('init', repo.name, cwd=parent)
                git('config', 'user.email', 'bogons@bogus.com', cwd=repo)
                git('config', 'user.name', 'Fake Name', cwd=repo)
                file.touch()
                git('add', 'test.txt', cwd=repo)
                git('commit', '-m', 'Initial commit', cwd=repo)
                chdir(repo)
                old = os.environ.get('GIT_CONFIG_GLOBAL')
                os.environ['GIT_CONFIG_GLOBAL'] = str(config)
                yield _GitRepository(path=repo / '.git')
                if old is None:
                    del os.environ['GIT_CONFIG_GLOBAL']
                else:
                    os.environ['GIT_CONFIG_GLOBAL'] = old
        yield from with_xgit(_t, 'xontrib.xgit.context')
        chdir(old)
        # Clean up, or try to: Windows is a pain
        with suppress(OSError):
            rmtree(tmp)
        try:
            Path(tmpname).rmdir()
        except OSError:
            with suppress(OSError):
                Path(tmpname).unlink()

@pytest.fixture()
def worktree(with_xgit, git, repository, chdir):
    '''
    Fixture to create a test worktree.
    '''
    def _t(*_, _GitWorktree, _GitCommit, _GitRef, **__):
        commit = git('rev-parse', 'HEAD', cwd=repository.path)
        branch = git('symbolic-ref', 'HEAD', cwd=repository.path)
        chdir(repository.path.parent)
        yield _GitWorktree(repository=repository,
                           path=repository.path.parent,
                           repository_path=repository.path,
                           branch=_GitRef(branch, repository=repository),
                           commit=_GitCommit(commit, repository=repository),
                           )
    yield from with_xgit(_t, 'xontrib.xgit.context', 'xontrib.xgit.objects')
