#!/usr/bin/env python3
#
# Copyright 2020 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import tempfile
import os
import sys
from pathlib import Path

def run(*command, capture=False, **kwargs):
    command = list(map(str, command))
    print(f'CMD:  {" ".join(command)}')
    stdout = subprocess.PIPE if capture else None
    result = subprocess.run(command, stdout=stdout, **kwargs)
    result.check_returncode()
    if capture:
        return result.stdout.decode('utf-8')
    return None

def git(*command, capture=False):
    return run('git', '-C', GIT_DIR, *command, capture=capture)

def step(title):
    print('=' * 80)
    print(title)
    print('-' * 80)


ROOT_DIR = Path(__file__).parent
GIT_DIR = ROOT_DIR  / '.v8'
DIST_DIR = ROOT_DIR / 'dist'
DOXYFILE_PATH = ROOT_DIR / 'Doxyfile'


step(f'Update V8 checkout in: {GIT_DIR}')
if not GIT_DIR.exists():
    GIT_DIR.mkdir()
    git('init')
    git('remote', 'add', 'origin', 'https://chromium.googlesource.com/v8/v8')
git('sparse-checkout', 'set', '--no-cone', '/include', '/samples')

step('List branches')
if len(sys.argv) == 1:
  NAMES = ['refs/heads/*-lkgr', 'refs/heads/lkgr']
else:
  NAMES = [
    'refs/heads/lkgr' if name == "head" else f'refs/heads/{name}-lkgr'
    for name in sys.argv[1:]
  ]

BRANCHES = git('ls-remote', '--heads', 'origin', *NAMES, capture=True).rstrip().split("\n")
BRANCHES = [ref.split('\t') for ref in BRANCHES if ref]
BRANCHES = [(ref.split('/')[-1].split('-')[0], sha) for sha, ref in BRANCHES]

# Sort branches from old to new:
BRANCHES.sort(key=lambda branch_and_sha: (float("inf"),) if branch_and_sha[0] == 'lkgr' else tuple(map(int, branch_and_sha[0].split('.'))))
print(BRANCHES)

DIST_DIR.mkdir(exist_ok=True)

for branch,sha in BRANCHES:
    step(f'Generating docs for branch: {branch}')
    if branch == 'lkgr':
        version_name = 'head'
    else:
        version_name = f'v{branch}'
    branch_dir = DIST_DIR / version_name
    branch_dir.mkdir(exist_ok=True)

    stamp = branch_dir / '.sha'

    def needs_update():
        if not stamp.exists():
            step(f'Needs update: no stamp file')
            return True
        stamp_mtime = stamp.stat().st_mtime
        if stamp_mtime <= DOXYFILE_PATH.stat().st_mtime:
            step(f'Needs update: stamp file older than Doxyfile')
            return True
        if stamp_mtime <= Path(__file__).stat().st_mtime:
            step(f'Needs update: stamp file older than update script')
            return True
        stamp_sha = stamp.read_text()
        if stamp_sha != sha:
            step(f'Needs update: stamp SHA does not match branch SHA ({stamp_sha} vs. {sha})')
            return True

        return False

    if not needs_update():
        step(f'Docs already up-to-date.')
        continue

    git('fetch', '--depth=1', '--no-tags', 'origin', sha)
    git('switch', '--force', '--detach', sha)
    git('clean', '--force', '-d')

    doxyfile_data = DOXYFILE_PATH.read_text()
    doxyfile_data += f"""
        PROJECT_NUMBER={version_name}
        HTML_OUTPUT={os.path.abspath(branch_dir)}
    """
    run('doxygen', '-', cwd=GIT_DIR, input=doxyfile_data.encode('utf-8'))
    stamp.write_text(sha)
