#!/usr/bin/env python3


import subprocess
import tempfile
import os
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


DESTINATION = Path(__file__).parent
GIT_DIR = DESTINATION  / '.v8'


step(f'Update V8 checkout in: {GIT_DIR}')
if not GIT_DIR.exists():
    run('git', 'clone', 'https://chromium.googlesource.com/v8/v8.git', GIT_DIR)
git('fetch', '--all')


step('List branches')
BRANCHES = git('branch', '--all', '--list', '*-lkgr', '--format=%(refname)', capture=True).split()
BRANCHES = list(set(map(lambda ref: ref.split('/')[-1], BRANCHES)))

# Sort branches from old to new:
BRANCHES.sort(key=lambda branch: list(map(int, branch.split('-')[0].split('.'))))
BRANCHES.append('lkgr')

# List of branches that have potential back-merges and thus need updates:
BRANCHES_FORCE_BUILDS = set(BRANCHES[-4:])
print(BRANCHES)



for branch in BRANCHES:
    step(f'Generating docs for branch: {branch}')
    if branch == 'lkgr':
        version_name = 'head'
    else:
        branch_name = branch.split('-')[0]
        version_name = f'v{branch_name}'
    branch_dir = DESTINATION / version_name
    branch_dir.mkdir(exist_ok=True)
    git('switch', '--force', '--detach', f'remotes/origin/{branch}')
    git('clean', '--force', '-d')
    doxyfile_path = DESTINATION / 'Doxyfile'
    with open(doxyfile_path) as doxyfile:
      doxyfile_data = doxyfile.read()
      doxyfile_data += f"\nPROJECT_NUMBER={version_name}"
      run('doxygen', '-', cwd=GIT_DIR, input=doxyfile_data.encode('utf-8'))
    source = GIT_DIR / 'html'
    run('rsync', '--itemize-changes', '--recursive',
            '--checksum', f'{source}{os.sep}', f'{branch_dir}{os.sep}')
    run('git', 'add', branch_dir)

