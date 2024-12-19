#!/usr/bin/env python3
'''
Script and code to zip and unzip a test repository.

Copies from a .git directory to a .zip file or vice versa.

When copying to a .git directory, the parent directory must be empty,
or newly created by the script.
'''

import os
import zipfile
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def chdir(path: Path):
    old = Path.cwd()
    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(old)

def unzip_repo(frm: Path, to: Path):
    to = to.resolve()
    frm = frm.resolve()
    if to.exists():
        raise ValueError(f'Target path exists: {to}')
    if to.name != '.git':
        raise ValueError(f'Target not a .git directory: {to}')
    worktree = to.parent
    worktree.mkdir(parents=False, exist_ok=True)
    for _ in to.parent.iterdir():
        raise ValueError(f'Target parent not empty: {worktree}')
    with zipfile.ZipFile(frm, 'r') as zipf:
        zipf.extractall(worktree)

def zip_repo(frm: Path, to: Path):
    to = to.resolve()
    frm = frm.resolve()
    if frm.name != '.git' or not (frm / 'HEAD').is_file():
        raise ValueError(f'Not a .git repository: {frm}')
    with (
        chdir(frm.parent),
        zipfile.ZipFile(to, 'w') as zipf
    ):
        for p in (d / f for d, _, fs in frm.walk()
                for f in fs):
            p = p.relative_to(frm.parent)
            print(p)
            zipf.write(p)


def main(frm: Path, to: Path):
    def ftype(f):
        if f.is_file():
            return 'file'
        if f.is_dir():
            return 'dir'
        return None
    
    def suffix(f):
        return f.name if f.name.startswith('.') else f.suffix
    
    match suffix(frm), ftype(frm), suffix(to), ftype(to):
        case '.zip', 'file', '', None:
            unzip_repo(frm, to)
        case '.zip', None, _, _:
            raise FileNotFoundError(f'Zip file not found: {frm}')
        case '.git', 'dir', '.zip', _:
            zip_repo(frm, to)
        case '', 'dir', '.zip', _:
            main(frm / '.git', to)
        case '.git', None, _, _:
            raise FileNotFoundError(f'.git directory not found: {frm}')
        case _, _, _, _:
            raise ValueError(
                f'Invalid arguments: '
                f'{suffix!r} '
                f'{ftype(frm)!r} '
                f'{suffix(to)!r} '
                f'{ftype(to)!r}'
            )

if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
    parser = ArgumentParser(
        description=__doc__,
        prog=Path(__file__).stem,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('frm',
                        type=Path,
                        help='Path to zip or directory to zip or unzip')
    parser.add_argument('to',
                        type=Path,
                        help='Path to zip or directory to zip or unzip')
    args = parser.parse_args()
    main(args.frm, args.to)


