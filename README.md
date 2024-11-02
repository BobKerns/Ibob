# xontrib-xgit

An [xonsh](https://xon.sh) command-line environment for exploring git repositories and histories. With [xgit](https://xon.sh/customization.html#updating-xonsh), you seamlessly blend displayed information and pythonic data manipulation, in the powerful python-native [xonsh](https://xon.sh) shell.

This provides a set of commands that return objects for both display and pythonic manipulation.

If you like the idea click ⭐ on the repo and <a href="https://twitter.com/intent/tweet?text=Nice%20xontrib%20for%20the%20xonsh%20shell!&url=https://github.com/BobKerns/xontrib-xgit" target="_blank">tweet</a>.

## Installation

To install use [xpip](https://xon.sh/customization.html#updating-xonsh):

```xsh
xpip install xontrib-xgit
# or: xpip install -U git+https://github.com/BobKerns/xontrib-xgit
```

## Usage

```xsh
xontrib load xgit
```

## Commands

### [`git-cd`](#git-cd-command) (Command)

> [`git-cd`](#git-cd-command) [`_path_`]`

Update the git working directory (and the process working directory if the directory exists in the worktree).

If _path_ is in a different worktree or repository, it will switch automatically to that worktree and repository.

With no arguments, returns to the root of the current repository.

### [`git-pwd`](xgit-pwd-command) (Command)

> [`git-pwd`](xgit-pwd-command)

Print information about the current git context, including:

- `repository`; Repository path per worktree
- `common`: Repository common path
- `worktree`: Worktree root path
- `git_path`: Path within the repository
- `branch`: Current Branch
- `commit`: Current commit
- `cwd`: Working directory (what `pwd` would print)

This just returns (and displays) the [`XGIT`](#xgit-variable) variable if it is not `None`. In scripts you can just reference this variable directly.

### [`XGIT`](#xgit-variable) (Variable)

The current `GitContext`. This is the same as the value returned from the [`git-pwd`](#git-pwd-command) command.

It will be `None` when not inside a git worktree or repository.

### [`XGIT_CONTEXTS`](#xgit_contexts-variable) (Variable)

A dictionary of `GitContext` objects, one for every worktree or repository we have visited.

This allows one to switch between repositories without losing context.

### [`git-ls`](#git-ls-command) (Command)

This returns the directory as an object which can be accessed from the python REPL:

```python
>>> git-ls .
_1: GitTree('998db2d22502eed36bd39653c8a793c22acd6687', len=14, '''
    - 998db2d22502eed36bd39653c8a793c22acd6687      441 .editorconfig
    - 998db2d22502eed36bd39653c8a793c22acd6687       36 .gitattributes
    D 998db2d22502eed36bd39653c8a793c22acd6687        - .github
    - 998db2d22502eed36bd39653c8a793c22acd6687     3207 .gitignore
    - 998db2d22502eed36bd39653c8a793c22acd6687       62 .markdownlint.json
    - 998db2d22502eed36bd39653c8a793c22acd6687      890 .pre-commit-config.yaml
    D 998db2d22502eed36bd39653c8a793c22acd6687        - .vscode
    - 998db2d22502eed36bd39653c8a793c22acd6687     1068 LICENSE
    - 998db2d22502eed36bd39653c8a793c22acd6687     4984 README.md
    - 998db2d22502eed36bd39653c8a793c22acd6687     5937 poetry.lock
    - 998db2d22502eed36bd39653c8a793c22acd6687     1675 pyproject.toml
    - 998db2d22502eed36bd39653c8a793c22acd6687       28 requirements.txt
    D 998db2d22502eed36bd39653c8a793c22acd6687        - tests
    D 998db2d22502eed36bd39653c8a793c22acd6687        - xontrib
''')
>>> _1['README.md']
_2: GitTreeEntry(
    GitBlob('1017942b1ddbcc52e35e4bdf9f28638464105d06', 4984),
    mode'100644',
    name='README.md')
>>>_2.object
_3: GitBlob('1017942b1ddbcc52e35e4bdf9f28638464105d06', 4984)
>>> _2.object.size
_4: 4984
>>> _2.size
_5: 4984
>>> _2.name
_6: 'README.md'
>>> _2.hash
_7: '1017942b1ddbcc52e35e4bdf9f28638464105d06'
```

At the first prompt, we type the 'git-ls' command. This returns an object which
displays the listing nicely as part of its pretty display.

Each line of the listing can be accessed as a `dict` (it is, in fact, a type of `dict`).
This includes iterating over keys or values.

The values in the dict are actually `GitTreeEntry` instances, which wrap the referenced
object with the additional information (name, and the file mode for the entry, which
conveys executable/link/regular file status for blobs).

However, `GitTreeEntry` instances proxy access to the underlying object, so you can mostly ignore the extra layer. The extra layer is needed because the same object may
appear in multiple trees under multiple names.

### [git_ls](#git_ls-function) (Function)

The functional version of the [`git-ls`](#git-ls-command) command.

```python
git_ls('xontrib-xgit')
```

This looks up the `GitTreeEntry` at the supplied path (default=`.`), and returns the underlying (`entry.object`).

The `GitTreeEntry` object itself is not returned, for a better display experience. It is presumed that you know where you started.

## Credits

This package was created with [xontrib template](https://github.com/xonsh/xontrib-template).

--------------------

## Xontrib Promotion (DO and REMOVE THIS SECTION)

- ✅ Check that your repository name starts from `xontrib-` prefix. It helps Github search find it.

- ✅ Add `xonsh`, `xontrib` and other thematic topics to the repository "About" setting.

- ✅ Add preview image in "Settings" - "Options" - "Social preview". It allows to show preview image in Github Topics and social networks e.g. Twitter.

- ✅ Enable "Sponsorship" in "Settings" - "Features" - Check "Sponsorships".

- Add xontrib to the [awesome-xontribs](https://github.com/xonsh/awesome-xontribs).

- ✅ Publish your xontrib to PyPi via Github Actions and users can install your xontrib via `xpip install xontrib-myxontrib`. Easiest way to achieve it is to use Github Actions. Register to [https://pypi.org/](https://pypi.org) and [create API token](https://pypi.org/help/#apitoken). Go to repository "Settings" - "Secrets" and your PyPI API token as `PYPI_API_TOKEN` as a "Repository Secret". Now when you create new Release the Github Actions will publish the xontrib to PyPi automatically. Release status will be in Actions section. See also `.github/workflows/release.yml`.

- Write a message to:
  - [xonsh Gitter chat](https://gitter.im/xonsh/xonsh?utm_source=xontrib-template&utm_medium=xontrib-template-promo&utm_campaign=xontrib-template-promo&utm_content=xontrib-template-promo),
  - [Twitter](https://twitter.com/intent/tweet?text=xonsh%20is%20a%20Python-powered,%20cross-platform,%20Unix-gazing%20shell%20language%20and%20command%20prompt.&url=https://github.com/BobKerns/xontrib-xgit),
  - [Reddit](https://www.reddit.com/r/xonsh),
  - [Mastodon](https://mastodon.online/).
