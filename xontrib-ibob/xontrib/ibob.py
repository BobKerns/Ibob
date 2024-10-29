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
from collections import defaultdict, Counter
from collections.abc import Callable
import builtins
import sys

from xonsh.built_ins import XSH, XonshSession
from xonsh.events import events
from xonsh.tools import chdir
from xonsh.procs.pipelines import HiddenCommandPipeline

__all__ = ()

# Good start! Get more documentation -> https://xon.sh/contents.html#guides

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

def _git_cd(path: str = '') -> None:
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
    except:
        print(f'Could not change to {fpath}')

def git_cd(args, stdin, stdout, stderr):
    if '--help' in args:
        print(getattr(_git_cd, '__doc__', ''))
        return
    _git_cd(*args)
    
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
    if args and '--help' in args:
        print(getattr(git_pwd, '__doc__', ''), file=stderr)
        return
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
    
def git_ls(args=['.'], stdin=None, stdout=None, stderr=None):
    """
    List the contents of the current directory or the directory provided.
    """
    if args and '--help' in args:
        print(getattr(git_ls, '__doc__', ''), file=stderr)
        return
    if GIT_CONTEXT is None:
        print('Not in a git repository', file=stderr)
        return
    if len(args) > 1:
        raise ValueError('Too many arguments')
    path = GIT_CONTEXT.repo_path / GIT_CONTEXT.git_path / Path(*args)
    path = path.resolve().relative_to(GIT_CONTEXT.repo_path)
    try:
        with chdir(GIT_CONTEXT.repo_path):
            parent: GitDir|None = None
            if path == Path('.'):
                tree = XSH.subproc_captured_stdout(['git', 'log', '--format=%T', '-n', '1', 'HEAD'])
            else:
                parent = git_ls([path.parent])
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
    events.ibob_on_predisplay.fire(value=value)
    sys.stdout.flush()
    _xonsh_displayhook(value)
    events.ibob_on_postdisplay.fire(value=value)

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
    value = XSH.ctx.get('_+', value)
    if value is not None and not isinstance(value, HiddenCommandPipeline):
        builtins._ =  value
        XSH.ctx['__'] = XSH.ctx['+']
        XSH.ctx['___'] = XSH.ctx['++']

@events.on_precommand
def pre_update_vars(cmd: str):
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
    xsh.aliases['git-ls'] = git_ls
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

def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
    """Clean up on unload."""
    print("Unloading xontrib-ibob", file=sys.stderr)
    sys.displayhook = _xonsh_displayhook
    def remove(event: str, func: Callable):
        try:
            getattr(events, event).remove(func)
        except ValueError:
            pass
        except KeyError:
            pass
    remove('on_precommand', pre_update_vars)
    remove('on_chdir', update_git_context)
    remove('ibob_on_predisplay', _ibob_on_predisplay)
    remove('ibob_on_postdisplay', _ibob_on_postdisplay)
    XSH.ctx['_#'] = _counter
    print("Unloaded xontrib-ibob", file=sys.stderr)
    