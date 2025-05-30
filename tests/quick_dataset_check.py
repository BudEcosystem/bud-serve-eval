#!/usr/bin/env python3

import subprocess
import json

def check_dataset_status():
    print("=== Dataset Download Status Check ===\n")
    
    # First, check if there are any dataset init pods running
    print("1. Checking for active dataset initialization pods:")
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "budeval", "--no-headers"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0 and result.stdout.strip():
        pods = result.stdout.strip().split('\n')
        dataset_pods = [p for p in pods if 'dataset' in p]
        if dataset_pods:
            print("   Found active dataset pods:")
            for pod in dataset_pods:
                print(f"   - {pod}")
                # Get logs from the pod
                pod_name = pod.split()[0]
                if 'init' in pod_name:
                    print(f"\n   Checking logs for {pod_name}:")
                    logs = subprocess.run(
                        ["kubectl", "logs", "-n", "budeval", pod_name, "--tail=5"],
                        capture_output=True, text=True
                    )
                    if logs.returncode == 0:
                        print("   " + logs.stdout.replace('\n', '\n   '))
        else:
            print("   No active dataset pods found")
    else:
        print("   No pods found in budeval namespace")
    
    # Check PVC status
    print("\n2. Checking PVC status:")
    result = subprocess.run(
        ["kubectl", "get", "pvc", "eval-datasets-pvc", "-n", "budeval", "-o", "json"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        pvc = json.loads(result.stdout)
        print(f"   PVC Status: {pvc['status']['phase']}")
        print(f"   Storage Class: {pvc['spec'].get('storageClassName', 'N/A')}")
        print(f"   Size: {pvc['spec']['resources']['requests']['storage']}")
        print(f"   Volume: {pvc['spec'].get('volumeName', 'Not bound')}")
    
    # Try to check the volume contents directly
    print("\n3. Attempting to check volume contents:")
    check_cmd = """
kubectl exec -n budeval -i $(kubectl get pods -n budeval -o name | head -1 | cut -d/ -f2) -- sh -c '
if [ -f /data/dataset_initialized ]; then
    echo "Dataset is INITIALIZED"
    cat /data/dataset_initialized
else
    echo "Dataset NOT initialized"
fi
' 2>/dev/null || echo "No running pods to check volume"
"""
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
    print(f"   {result.stdout.strip()}")
    
    print("\n4. Quick check using a temporary pod:")
    # Create a minimal pod just to check the file
    check_pod = subprocess.run([
        "kubectl", "run", "quick-check", "-n", "budeval", 
        "--rm", "-i", "--restart=Never", "--image=busybox",
        "--", "sh", "-c", 
        "mount | grep eval-datasets && echo 'Volume mounted' || echo 'Volume not accessible'"
    ], capture_output=True, text=True)
    
    if check_pod.returncode == 0:
        print(f"   {check_pod.stdout.strip()}")

if __name__ == "__main__":
    check_dataset_status()