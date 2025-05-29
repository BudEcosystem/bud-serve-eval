#!/usr/bin/env python3
"""Check if the eval-datasets volume exists."""

import subprocess
import json
import sys
from pathlib import Path

def check_volume_with_kubectl():
    """Check volume using kubectl."""
    print("Checking eval-datasets volume with kubectl...")
    
    try:
        # Check PV
        result = subprocess.run(
            ["kubectl", "get", "pv", "eval-datasets", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pv = json.loads(result.stdout)
            print(f"✓ PV exists: {pv['metadata']['name']}")
            print(f"  Status: {pv['status']['phase']}")
            print(f"  Size: {pv['spec']['capacity']['storage']}")
        else:
            print("✗ PV does not exist")
        
        # Check PVC
        result = subprocess.run(
            ["kubectl", "get", "pvc", "eval-datasets-pvc", "-n", "budeval", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pvc = json.loads(result.stdout)
            print(f"✓ PVC exists: {pvc['metadata']['name']}")
            print(f"  Status: {pvc['status']['phase']}")
            print(f"  Namespace: {pvc['metadata']['namespace']}")
        else:
            print("✗ PVC does not exist")
            
    except Exception as e:
        print(f"Error checking with kubectl: {e}")

def check_volume_with_k3s():
    """Check volume using k3s kubectl."""
    print("\nChecking eval-datasets volume with k3s kubectl...")
    
    try:
        # Check PV
        result = subprocess.run(
            ["sudo", "k3s", "kubectl", "get", "pv", "eval-datasets", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pv = json.loads(result.stdout)
            print(f"✓ PV exists: {pv['metadata']['name']}")
            print(f"  Status: {pv['status']['phase']}")
            print(f"  Size: {pv['spec']['capacity']['storage']}")
        else:
            print("✗ PV does not exist")
        
        # Check PVC
        result = subprocess.run(
            ["sudo", "k3s", "kubectl", "get", "pvc", "eval-datasets-pvc", "-n", "budeval", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pvc = json.loads(result.stdout)
            print(f"✓ PVC exists: {pvc['metadata']['name']}")
            print(f"  Status: {pvc['status']['phase']}")
            print(f"  Namespace: {pvc['metadata']['namespace']}")
        else:
            print("✗ PVC does not exist")
            
    except Exception as e:
        print(f"Error checking with k3s: {e}")

def check_host_path():
    """Check if the host path exists."""
    print("\nChecking host path...")
    host_path = Path("/tmp/budeval-volumes/eval-datasets")
    
    if host_path.exists():
        print(f"✓ Host path exists: {host_path}")
        print(f"  Is directory: {host_path.is_dir()}")
        
        # Check permissions
        try:
            result = subprocess.run(["ls", "-la", str(host_path)], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  Contents:\n{result.stdout}")
        except:
            pass
    else:
        print(f"✗ Host path does not exist: {host_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("Checking eval-datasets volume status")
    print("=" * 60)
    
    # Try kubectl first
    check_volume_with_kubectl()
    
    # Try k3s kubectl
    check_volume_with_k3s()
    
    # Check host path
    check_host_path()
    
    print("=" * 60)