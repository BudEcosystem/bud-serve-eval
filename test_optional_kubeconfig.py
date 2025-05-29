#!/usr/bin/env python3
"""Test script to verify optional kubeconfig functionality."""

import json
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


def test_optional_kubeconfig():
    """Test that the orchestrator handles optional kubeconfig correctly."""
    
    print("Testing optional kubeconfig functionality...")
    
    # Initialize orchestrator
    orchestrator = AnsibleOrchestrator()
    
    # Test 1: With kubeconfig (simulating local environment)
    print("\n1. Testing with kubeconfig (local environment)...")
    try:
        # Mock kubeconfig - this would normally come from the request
        mock_kubeconfig = json.dumps({
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": "test-cluster", "cluster": {"server": "https://localhost:6443"}}],
            "contexts": [{"name": "test-context", "context": {"cluster": "test-cluster", "user": "test-user"}}],
            "current-context": "test-context",
            "users": [{"name": "test-user", "user": {"token": "test-token"}}]
        })
        
        # This should work with kubeconfig
        result = orchestrator.verify_cluster_connection(mock_kubeconfig)
        print(f"Result with kubeconfig: {result}")
        
    except Exception as e:
        print(f"Error with kubeconfig: {e}")
    
    # Test 2: Without kubeconfig (simulating in-cluster environment)
    print("\n2. Testing without kubeconfig (in-cluster environment)...")
    try:
        # This should work without kubeconfig if running in-cluster
        result = orchestrator.verify_cluster_connection(None)
        print(f"Result without kubeconfig: {result}")
        
    except Exception as e:
        print(f"Error without kubeconfig: {e}")
        print("This is expected if not running in a Kubernetes cluster")
    
    # Test 3: Check environment detection
    print("\n3. Checking environment...")
    in_cluster = os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token')
    print(f"Running in Kubernetes cluster: {in_cluster}")
    
    if in_cluster:
        print("In-cluster config should be used when kubeconfig is None")
    else:
        print("Kubeconfig is required when running outside of cluster")
    
    print("\nTest completed!")


if __name__ == "__main__":
    test_optional_kubeconfig()