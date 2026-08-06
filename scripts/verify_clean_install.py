#!/usr/bin/env python3
"""Verify RecoveryLab wheel installs and works from a completely clean environment."""

import venv, subprocess, os, sys, shutil

venv_dir = '/tmp/recoverylab-clean-test-venv'
if os.path.exists(venv_dir):
    shutil.rmtree(venv_dir)

print('=' * 60)
print('VERIFICATION 3: Wheel installs from clean environment')
print('=' * 60)

print('Creating clean virtual environment...')
venv.create(venv_dir, with_pip=True)

pip = os.path.join(venv_dir, 'bin', 'pip')
python = os.path.join(venv_dir, 'bin', 'python')

# Install from the built wheel
print('Installing from local wheel...')
result = subprocess.run(
    [pip, 'install', '/home/z/my-project/download/recoverylab-0.6.0-py3-none-any.whl'],
    capture_output=True, text=True, timeout=120
)
print(f'  pip install exit code: {result.returncode}')
if result.returncode != 0:
    print(f'  STDERR: {result.stderr[-500:]}')
    sys.exit(1)
else:
    for line in result.stdout.strip().split('\n')[-3:]:
        print(f'  {line}')

# Verify import works
print()
print('Testing import...')
result2 = subprocess.run(
    [python, '-c', 'from core import RecoveryEngine, __version__; print(f"RecoveryEngine imported. Version: {__version__}")'],
    capture_output=True, text=True, timeout=30
)
print(f'  Import exit code: {result2.returncode}')
print(f'  Output: {result2.stdout.strip()}')
if result2.returncode != 0:
    print(f'  Error: {result2.stderr.strip()[-300:]}')

# Verify CLI entry point
print()
print('Testing CLI entry point...')
recoverylab_cli = os.path.join(venv_dir, 'bin', 'recoverylab')
if os.path.exists(recoverylab_cli):
    result3 = subprocess.run(
        [recoverylab_cli, '--version'],
        capture_output=True, text=True, timeout=30
    )
    print(f'  CLI --version exit code: {result3.returncode}')
    print(f'  Output: {result3.stdout.strip()}')
else:
    print(f'  CLI entry point NOT FOUND at {recoverylab_cli}')
    print(f'  Checking scripts in venv/bin...')
    bins = [f for f in os.listdir(os.path.join(venv_dir, 'bin')) if not f.startswith('_') and f not in ('python', 'python3', 'pip', 'activate', 'Activate.ps1', 'Activate.csh', 'Activate.fish', 'pip3')]
    print(f'  Available: {bins}')

print()
print('Done.')
