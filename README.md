# xontrib-git-explorer

An [xonsh](https://xon.sh) command-line environment for exploring git repositories and histories.

## Commands

### git-cd (Command)

`git-cd [`_path_`]`

Update the git working directory (and the process working directory if the directory exists in the worktree).

With no arguments, returns to the root of the current repository.

### git-pwd (Command)

`git-pwd`

Print information about the current git context, including:

- Repository path
- Worktree root path
- Path within the repository
- Current Branch
- Current commit
- Working directory (what `pwd` would print)

### git-ls (Command)

`git-ls [`_path_`]`

List the entries at the current location in the current tree. If _path_is supplied, lists the entries relative to the current location.

This returns the directory as an object which can be accessed from the python REPL:

```bash
>>> git-ls
_3: GitDir(c000f7a0a713b405fe0de6531fdbdfff3ff65d38)[7]
    - 569f95766c26158241a665763c76b93b103538b9     3207 .gitignore
    D 46b57ab337456176669e75513dbe0f5eeca38a22        1 .vscode
    - a3990ed1209000756420fae0ee6386e051204a60     1066 LICENSE
    - 505d8917cd9697185e30bb79238be4d84d02693e       50 README.md
    D 6f0c75cd8b53eeb83198dd5c6caea5361a240e20        2 iBob
    - 16494e4075e5cc44c5a928c7a325b8bc7bf552d5       23 requirements.txt
    D 05433255eddde7d3261f07a45b857374e6087278       10 xontrib-ibob
>>> _['README.md']
GitFile(- 505d8917cd9697185e30bb79238be4d84d02693e       50)
>>> _.hash
'505d8917cd9697185e30bb79238be4d84d02693e'
```

### git_ls (Function)

The functional version of the `git-ls` command.

```python
git_ls('xontrib-ibob')
```
