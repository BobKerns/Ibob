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
    match frm.suffix, frm.is_file(), to.suffix, to.is_file():
        case '.zip', True, '', False:
            unzip_repo(frm, to)
        case '', False, '.zip', _:
            zip_repo(frm, to)
        case _, _, _, _:
            raise ValueError(
                f'Invalid arguments: '
                f'{frm.suffix!r} '
                f'{frm.is_file()!r} '
                f'{to.suffix!r} '
                f'{to.is_file()!r}'
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
    
    
        