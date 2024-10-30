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
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, cast, Any
from collections import defaultdict
from collections.abc import Callable
import builtins
import sys
import io
from inspect import signature, Signature
from functools import wraps

from xonsh.built_ins import XSH, XonshSession
from xonsh.events import events
from xonsh.tools import chdir
from xonsh.procs.pipelines import HiddenCommandPipeline

__all__ = ()

# Good start! Get more documentation -> https://xon.sh/contents.html#guides

_aliases: dict[str: Any] = {}
"""
Dictionary of aliases defined here to be unloaded if this is unloaded.
"""
_exports: dict[str: Callable] = {}
"""
Dictionary of functions defined here to be unloaded if this is unloaded.
"""

def command(cmd: Optional[Callable]=None,
            flags: set=set(),
            for_value: bool=False,
            alias: Optional[str] = None,
            export: bool=False,
            ) -> Callable:
    """
    Decorator/decorator factory to make a function a command. Command-line
    flags and arguments are passed to the function as keyword arguments.
    
    - `flags` is a set of strings that are considered flags. Flags do not
    take arguments. If a flag is present, the value is True.
    
    - If `for_value` is True, the function's return value is used as the
    return value of the command. Otherwise, the return value will be
    a hidden command pipeline.
    
    - `alias` gives an alternate name for the command. Otherwise a name is
    constructed from the function name.
    
    - `export` makes the function available from python as well as a command.
    
    EXAMPLES:
    
    @command
    def my_command(args, stdin, stdout, stderr):
        ...
    
    @command(flags={'a', 'b'})
    def my_command(args, stdin, stdout, stderr):
        ...
    
    @command(for_value=True)
    def my_command(*args, **kwargs):
        ...
    """
    if cmd is None:
        return lambda cmd: command(cmd,
                                   flags=flags,
                                   for_value=for_value,
                                   alias=alias,
                                   export=export,
                                   ) 
    if alias is None:
        alias = cmd.__name__.replace('_', '-')
    def wrapper(args,
                stdin: io.TextIOBase=sys.stdin,
                stdout: io.TextIOBase=sys.stdout,
                stderr: io.TextIOBase=sys.stderr,
                **kwargs):
        if '--help' in args:
            print(getattr(cmd, '__doc__', ''), file=stderr)
            return
        while len(args) > 0:
            if args[0] == '--':
                args.pop(0)
                break
            if args[0].startswith('--'):
                if '=' in args[0]:
                    k, v = args.pop(0).split('=', 1)
                    kwargs[k[2:]] = v
                else:
                    if args[0] in flags:
                        kwargs[args.pop(0)[2:]] = True
                    else:
                        kwargs[args.pop(0)[2:]] = args.pop(0)
            else:
                break
            
        sig: Signature = signature(cmd)
        n_args = []
        n_kwargs = {}
        for p in sig.parameters.values():
            def add_arg(value: Any):
                match p.kind:
                    case p.POSITIONAL_ONLY:
                            n_args.append(value)
                    case p.POSITIONAL_OR_KEYWORD:
                        positional = len(args) > 0
                        if value == p.empty:
                            if positional:
                                value = args.pop(0)
                            elif p.name in kwargs:
                                value = kwargs.pop(p.name)
                            else:
                                value = p.default
                        if value == p.empty:
                            raise ValueError(f'Missing value for {p.name}')
                        if positional:
                            n_args.append(value)
                        else:
                            n_kwargs[p.name] = value
                    case p.KEYWORD_ONLY:
                        if value == p.empty:
                            if p.name in kwargs:
                                value = kwargs.pop(p.name)
                            else:
                                value = p.default
                        if value == p.empty:
                            raise ValueError(f'Missing value for {p.name}')
                        n_kwargs[p.name] = value
                    case p.VAR_POSITIONAL:
                        if len(args) > 0:
                            n_args.extend(args)
                            args.clear()
                    case p.VAR_KEYWORD:
                        n_args.update({
                            "stdin": stdin, 
                            "stdout": stdout,
                            "stderr": stderr
                        })
            match p.name:
                case 'stdin': add_arg(stdin)
                case 'stdout': add_arg(stdout)
                case 'stderr': add_arg(stderr)
                case 'args': add_arg(args)
                case _: add_arg(kwargs.get(p.name, p.empty))
        try:
            val = cmd(*n_args, **n_kwargs)
            if for_value:
                XSH.ctx['_+'] = val
        except Exception as ex:
            print(f'Error running {alias}: {ex}', file=stderr)
        return ()
    # @wrap(cmd) copies the signature, which we don't want.
    wrapper.__name__ = cmd.__name__
    wrapper.__qualname__ = cmd.__qualname__
    wrapper.__doc__ = cmd.__doc__
    wrapper.__module__ = cmd.__module__
    _aliases[alias] = XSH.aliases.get(alias)
    XSH.aliases[alias] = wrapper
    if export:
        _exports[cmd.__name__] = XSH.ctx.get(cmd.__name__)
        XSH.ctx[cmd.__name__] = cmd
    return cmd

type ContextKey = tuple[Path, Path, str, str]
@dataclass
class GitContext:
    repo_path: Path = Path('.')
    git_path: Path = Path('.')
    branch: str = ''
    commit: str = ''
    def loc(self, subpath: Optional[Path|str]=None) -> ContextKey:
        if subpath is None:
            return (self.repo_path, self.git_path, self.branch, self.commit)
        return (self.repo_path, subpath, self.branch, self.commit)
    def new_context(self, /,
                    repo_path: Optional[Path]=None,
                    git_path: Optional[Path]=None,
                    branch: Optional[str] = None,
                    commit: Optional[str] = None,
                    ) -> 'GitContext':
        repo_path = repo_path or self.repo_path
        git_path = git_path or self.git_path
        branch = branch if branch is not None else self.branch
        commit = commit or self.commit
        return GitContext(repo_path, git_path, branch, commit)
        

GIT_CONTEXTS: dict[Path, GitContext] = {}

def _set_git_context():
    global GIT_CONTEXT
    try:
        _repo = Path((XSH.subproc_captured_stdout(['git', 'rev-parse', '--show-toplevel'])))
        if _repo in GIT_CONTEXTS:
            XSH.ctx['GIT_CONTEXT'] = GIT_CONTEXT = GIT_CONTEXTS[_repo]
            return GIT_CONTEXT
        GIT_CONTEXTS[_repo] = XSH.ctx['GIT_CONTEXT'] = GIT_CONTEXT = GitContext(
            repo_path=_repo,
            git_path=Path.cwd().relative_to(_repo),
            commit=XSH.subproc_captured_stdout(['git', 'rev-parse', 'HEAD']),
            branch=XSH.subproc_captured_stdout(['git', 'name-rev', '--name-only', 'HEAD'])
            )
    except:
        XSH.ctx['GIT_CONTEXT'] = GIT_CONTEXT = None
    return GIT_CONTEXT

GIT_CONTEXT = _set_git_context()

@command(export=True)
def git_cd(path: str = '', stderr=sys.stderr) -> None:
    """
    Change the current working directory to the path provided.
    If no path is provided, change the current working directory to the git repository root.
    """
    if GIT_CONTEXT is None:
        XSH.execer.exec(f'cd {path}')
        return
    if path == '':
        GIT_CONTEXT.git_path = Path('.')
    elif path == '.':
        pass
    else:
        git_path = (GIT_CONTEXT.repo_path / GIT_CONTEXT.git_path / path).resolve()
        git_path = git_path.relative_to(GIT_CONTEXT.repo_path)
        GIT_CONTEXT.git_path = git_path
    fpath = GIT_CONTEXT.repo_path / GIT_CONTEXT.git_path
    try:
        XSH.execer.exec(f'cd {fpath}')
    except Exception as ex:
        print(f'Could not change to {fpath}: {ex}', file=stderr)
    
def relative_to_home(path: Path) -> Path:
    """
    Get a path for display relative to the home directory.
    This is for display only.
    """
    home = Path.home()
    if path == home:
        return Path('~')
    if path == home.parent:
        return Path(f'~{home.name}')
    try:
        return Path('~') / path.relative_to(home)
    except ValueError:
        return path

def git_pwd(args=None, stdin=None, stdout=None, stderr=None):
    """
    Print the current working directory and git context information if available.
    """
    if GIT_CONTEXT is None:
        print(f'cwd: {relative_to_home(Path.cwd())}', file=stdout)
        print('Not in a git repository', file=stdout)
        return
    print(f'repo: {relative_to_home(GIT_CONTEXT.repo_path)}', file=stdout)
    print(f'path: {GIT_CONTEXT.git_path}', file=stdout)
    print(f'branch: {GIT_CONTEXT.branch}', file=stdout)
    print(f'commit: {GIT_CONTEXT.commit}', file=stdout)
    print(f'cwd: {relative_to_home(Path.cwd())}', file=stdout)
    
class GitEntry:
    def __init__(self, mode: str, type: str, hash: str):
        self.mode = mode
        self.type = type
        self.hash = hash
    def __hash__(self):
        return hash(self.hash)
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.hash == other.hash

def git_entry(line: str, context: GitContext=GIT_CONTEXT, parent: str|None=None) -> GitEntry:
    mode, type, hash, size, name = line.split()
    entry = GIT_ENTRIES.get(hash)
    if entry is not None:
        return name, entry
    if type == 'tree':
        entry = GitDir(hash, context)
    elif type == 'blob':
        entry = GitFile(mode, hash, size)
    else:
        # We don't currently handle tags or commits (submodules)
        raise ValueError(f'Unknown type {type}')
    GIT_ENTRIES[hash] = entry
    key = (context.loc(name), parent)
    GIT_REFERENCES[hash].add(key)
    return name, entry

type GitLoader = Callable[[], None]

class GitDir(GitEntry, dict[str, GitEntry]):
    _lazy_loader: GitLoader
    
    def __init__(self, tree: str, context: GitContext):
        GitEntry.__init__(self, '0400', 'tree', tree)
        dict.__init__(self)
        def _lazy_loader():
            nonlocal context
            context = context.new_context()
            with chdir(context.repo_path):
                cmd = ['git', 'ls-tree', '--long', tree]
                for line in XSH.subproc_captured_object(cmd).itercheck():
                    if line:
                        name, entry = git_entry(line, context, tree)
                        dict.__setitem__(self, name, entry)
        self._lazy_loader = _lazy_loader
    
    def __repr__(self):
        return f"""GitDir(hash={self.hash})"""
    
    def _expand(self):
        if super().__len__() > 0:
            return
        self._lazy_loader()

    def __len__(self):
        if super().__len__() == 0:
            self._expand()
        return super().__len__()
    
    def __contains__(self, key):
        self._expand()
        return super().__contains__(key)
    
    def __getitem__(self, key: str) -> GitEntry:
        self._expand()
        return super().__getitem__(key)
    
    def __setitem__(self, key: str, value: GitEntry):
        raise NotImplementedError('Cannot set items in a GitDir')
    
    def __delitem__(self, key: str):
        raise NotImplementedError('Cannot delete items in a GitDir')
    
    def __iter__(self):
        self._expand()
        return super().__iter__()
    
    def __bool__(self):
        return True
    
    def __reversed__(self):
        self._expand()
        return super().__reversed__()
    
    def __str__(self):
        import traceback
        traceback.print_stack(file=sys.stderr)
        sys.stderr.flush()
        return f'D {self.hash} {len(self):>8d}'
    
    def __format__(self, fmt: str):
        """
        Format a directory for display.
        Format specifier is in two parts separated by a colon.
        The first part is a format string for the entries.
        The second part is a path to the directory.
        
        The first part can contain:
        - 'r' to format recursively
        - 'l' to format the entries in long format.
        - 'a' to abbreviate the hash to 8 characters.
        - 'd' to format the directory as itself
        - 'n' to include only the entry names, not the full paths.
        """
        dfmt, *rest = fmt.split(':', 1)
        path = rest[0] if rest else ''
        def dpath(name: str) -> str:
            if 'n' not in dfmt:
                return f'{path}/{name}'
        if 'r' in dfmt:
            return '\n'.join(e.__format__(f'{dfmt}:{dpath(n)}') for n,e in self.items())
        if 'l' in dfmt and not 'd' in dfmt:
            return '\n'.join(e.__format__(f'd{dfmt}:{dpath(n)}') for n,e in self.items())
        hash = self.hash[:8] if 'a' in dfmt else self.hash
        return f'D {hash} {len(self):>8d}'
    
    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text(f'GitDir({self.hash})')
        else:
            with p.group(4, f'GitDir({self.hash})[{len(self)}]'):
                for n, e in self.items():
                    p.breakable()
                    p.text(f'{e:ld} {n}')

class GitFile(GitEntry):
    """
    A file ("blob") stored in a git repository.
    """
    size: int
    "Size in bytes of the file."
    
    def __init__(self, mode, hash, size):
        super().__init__(mode, 'blob', hash)
        self.size = int(size)
    def __str__(self):
        rw = 'X' if self.mode == '100755' else '-'
        return f'{rw} {self.hash} {self.size:>8d}'
    def __repr__(self):
        return f'GitFile({str(self)})'
    def __len__(self):
        return self.size
    def __format__(self, fmt: str):
        """
        Format a file for display.
        Format specifier is in two parts separated by a colon.
        The first part is a format string for the output.
        The second part is a path to the file.
        
        As files don't have inherent names, the name must be provided in the format string
        by the directory that contains the file. If no path is provided, the hash is used.
        
        The format string can contain:
        - 'l' to format the file in long format.
        """
        dfmt, *rest = fmt.split(':', 1)
        path = f' {rest[0]}' if rest else ''
        rw = 'X' if self.mode == '100755' else '-'
        hash = self.hash[:8] if 'a' in dfmt else self.hash
        if 'l' in dfmt:
            return f'{rw} {hash} {self.size:>8d}{path}'
        return path or hash

GIT_ENTRIES: dict[str, GitEntry] = {}
"""
All the git entries we have seen.
"""

type GitObjectReference = tuple[ContextKey, GitDir|None]
"""
A reference to a git object in a tree in a repository.
"""

GIT_REFERENCES: dict[str, set[GitObjectReference]] = defaultdict(set)
"""
A map to where an object is referenced.
"""

@command(for_value=True,
         export=True)
def git_ls(path: Path|str = '.', stderr=sys.stderr):
    """
    List the contents of the current directory or the directory provided.
    """
    path = GIT_CONTEXT.repo_path / GIT_CONTEXT.git_path / path
    path = path.resolve().relative_to(GIT_CONTEXT.repo_path)
    try:
        with chdir(GIT_CONTEXT.repo_path):
            parent: GitDir|None = None
            if path == Path('.'):
                tree = XSH.subproc_captured_stdout(['git', 'log', '--format=%T', '-n', '1', 'HEAD'])
            else:
                parent = git_ls(path.parent)
                print(f'{path.name=} {path.parent=} {parent=}')
                tree = parent[path.name].hash
            dir = cast(GitDir, GIT_ENTRIES.get(tree))
            if dir is None:
                dir = GitDir(tree, GIT_CONTEXT)
                GIT_ENTRIES[tree] = dir
            key = (GIT_CONTEXT.loc(path), parent.hash if parent else None)
            GIT_REFERENCES[tree].add(key)
            XSH.ctx['_+'] = dir
            return dir

    except Exception as ex:
        print(ex, file=stderr)
        return None
    
events.doc('ibob_on_predisplay', 'Runs before displaying the result of a command. Receives the value to be displayed.')
events.doc('ibob_on_postdisplay', 'Runs after displaying the result of a command. Receives C the value displayed.')

_xonsh_displayhook = sys.displayhook
def _ibob_displayhook(value: Any):
    """
    Add handling for value-returning commands, pre- and post-display events,
    and exception protection.
    """
    ovalue = value
    if isinstance(value, HiddenCommandPipeline):
        value = XSH.ctx.get('_+', value)
    sys.stderr.flush()
    try:
        events.ibob_on_predisplay.fire(value=value)
        sys.stdout.flush()
        _xonsh_displayhook(value)
        events.ibob_on_postdisplay.fire(value=value)
    except Exception as ex:
        print(ex, file=sys.stderr)
        sys.stderr.flush()

sys.displayhook = _ibob_displayhook

_counter = XSH.ctx.get('_#', iter(range(sys.maxsize)))
_count: int  = next(_counter)

@events.ibob_on_predisplay
def _ibob_on_predisplay(value: Any):
    global _count
    if value is not None and not isinstance(value, HiddenCommandPipeline):
        _count = next(_counter)
        XSH.ctx['_#'] = _count
        ivar = f'_i{_count}'
        ovar = f'_{_count}'
        XSH.ctx[ivar] = XSH.ctx['-']
        XSH.ctx[ovar] = value
        print(f'{ovar}: ', end='')

@events.ibob_on_postdisplay
def _ibob_on_postdisplay(value: Any):
    if value is not None and not isinstance(value, HiddenCommandPipeline):
        builtins._ =  value
        XSH.ctx['__'] = XSH.ctx['+']
        XSH.ctx['___'] = XSH.ctx['++']

@events.on_precommand
def _on_precommand(cmd: str):
    if '_+' in XSH.ctx:
        del XSH.ctx['_+']
    XSH.ctx['-'] = cmd.strip()
    XSH.ctx['+'] = builtins._
    XSH.ctx['++'] = XSH.ctx.get('__')
    XSH.ctx['+++'] = XSH.ctx.get('___')
    
@events.on_chdir
def update_git_context(olddir, newdir):
    if GIT_CONTEXT is None:
        _set_git_context()
        return
    newpath = Path(newdir)
    if GIT_CONTEXT.repo_path == newpath:
        GIT_CONTEXT.git_path = Path('.')
    if GIT_CONTEXT.repo_path not in newpath.parents:
        _set_git_context()
    else:
        GIT_CONTEXT.git_path = Path(newdir).resolve().relative_to(GIT_CONTEXT.repo_path)

def _load_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """
    this function will be called when loading/reloading the xontrib.

    Args:
        xsh: the current xonsh session instance, serves as the interface to manipulate the session.
             This allows you to register new aliases, history backends, event listeners ...
        **kwargs: it is empty as of now. Kept for future proofing.
    Returns:
        dict: this will get loaded into the current execution context
    """
    xsh.aliases['git-cd'] = git_cd
    xsh.aliases['git-pwd'] = git_pwd
    xsh.ctx['+'] = None
    xsh.ctx['++'] = None
    xsh.ctx['+++'] = None
    xsh.ctx['-'] = None
    xsh.ctx['__'] = None
    xsh.ctx['___'] = None
    print("Loaded xontrib-ibob", file=sys.stderr)
    return {
        'GIT_CONTEXT': GIT_CONTEXT,
        'GIT_CONTEXTS': GIT_CONTEXTS,
        'GIT_ENTRIES': GIT_ENTRIES,
        'GIT_REFERENCES': GIT_REFERENCES,
    }
    
def unload(env: dict[str, Any], name: str, value = None):
    """
    Unload a value supplied by the xontrib.
    """
    try:
        if value is None:
            if name in env:
                del env[name]
        else:
            env[name] = value
    except Exception as ex:
        print(f'Error unloading {name}: {ex}', file=sys.stderr)
    
def unload_exports(env: dict[str, Any], exports: dict[str, Callable]):
    for k,v in exports.items():
        unload(env, k, v)

def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """Clean up on unload."""
    print("Unloading xontrib-ibob", file=sys.stderr)
    unload_exports(xsh.ctx, _exports)
    unload_exports(xsh.aliases, _aliases)
    unload(XSH.ctx, 'GIT_CONTEXT')
    unload(XSH.ctx, 'GIT_CONTEXTS')
    unload(XSH.ctx, 'GIT_ENTRIES')
    unload(XSH.ctx, 'GIT_REFERENCES')
    
    sys.displayhook = _xonsh_displayhook
    def remove(event: str, func: Callable):
        try:
            getattr(events, event).remove(func)
        except ValueError:
            pass
        except KeyError:
            pass
    remove('on_precommand', _on_precommand)
    remove('on_chdir', update_git_context)
    remove('ibob_on_predisplay', _ibob_on_predisplay)
    remove('ibob_on_postdisplay', _ibob_on_postdisplay)
    XSH.ctx['_#'] = _counter
    print("Unloaded xontrib-ibob", file=sys.stderr)
    