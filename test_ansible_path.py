#!/usr/bin/env python3
"""Test script to verify ansible-runner can find ansible-playbook."""

import sys
import os
import subprocess

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

# Check if we're in the virtual environment
venv_bin = os.path.dirname(sys.executable)
print(f"Virtual environment bin: {venv_bin}")

# Check if ansible-playbook exists
ansible_playbook_path = os.path.join(venv_bin, "ansible-playbook")
print(f"Ansible playbook path: {ansible_playbook_path}")
print(f"Exists: {os.path.exists(ansible_playbook_path)}")

# Try to run ansible-playbook --version
try:
    result = subprocess.run([ansible_playbook_path, "--version"], capture_output=True, text=True)
    print(f"\nAnsible playbook version:")
    print(result.stdout)
except Exception as e:
    print(f"Error running ansible-playbook: {e}")

# Check PATH
print(f"\nCurrent PATH: {os.environ.get('PATH', 'Not set')}")

# Test with updated PATH
updated_path = f"{venv_bin}:{os.environ.get('PATH', '')}"
print(f"\nUpdated PATH: {updated_path}")

# Try to run with updated PATH
env = os.environ.copy()
env['PATH'] = updated_path
try:
    result = subprocess.run(["ansible-playbook", "--version"], capture_output=True, text=True, env=env)
    print(f"\nAnsible playbook with updated PATH:")
    print(result.stdout)
except Exception as e:
    print(f"Error running ansible-playbook with updated PATH: {e}")