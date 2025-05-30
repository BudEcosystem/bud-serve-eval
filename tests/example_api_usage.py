#!/usr/bin/env python3
"""Example showing how to use the evaluation API with optional kubeconfig."""

import json
import requests

# Base URL of the evaluation service
BASE_URL = "http://100.84.162.116:8099"

def example_start_evaluation_with_kubeconfig():
    """Example: Start evaluation with kubeconfig (for local/external use)."""
    print("1. Starting evaluation WITH kubeconfig...")
    
    payload = {
        "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
        "model_name": "gpt-4",
        "api_key": "sk-...",
        "base_url": "https://api.openai.com/v1",
        "kubeconfig": json.dumps({
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": "my-cluster", "cluster": {"server": "https://k8s.example.com"}}],
            "contexts": [{"name": "my-context", "context": {"cluster": "my-cluster", "user": "my-user"}}],
            "current-context": "my-context",
            "users": [{"name": "my-user", "user": {"token": "my-token"}}]
        })
    }
    
    response = requests.post(f"{BASE_URL}/evals/start", json=payload)
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


def example_start_evaluation_without_kubeconfig():
    """Example: Start evaluation without kubeconfig (for in-cluster use)."""
    print("\n2. Starting evaluation WITHOUT kubeconfig (in-cluster)...")
    
    payload = {
        "eval_request_id": "123e4567-e89b-12d3-a456-426614174001",
        "model_name": "gpt-4",
        "api_key": "sk-...",
        "base_url": "https://api.openai.com/v1"
        # Note: kubeconfig is omitted - will use in-cluster config
    }
    
    response = requests.post(f"{BASE_URL}/evals/start", json=payload)
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


def example_get_status_with_kubeconfig():
    """Example: Get job status with kubeconfig."""
    print("\n3. Getting job status WITH kubeconfig...")
    
    job_id = "eval-123e4567-e89b-12d3-a456-426614174000"
    kubeconfig = json.dumps({
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "my-cluster", "cluster": {"server": "https://k8s.example.com"}}],
        "contexts": [{"name": "my-context", "context": {"cluster": "my-cluster", "user": "my-user"}}],
        "current-context": "my-context",
        "users": [{"name": "my-user", "user": {"token": "my-token"}}]
    })
    
    response = requests.get(f"{BASE_URL}/evals/status/{job_id}", params={"kubeconfig": kubeconfig})
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


def example_get_status_without_kubeconfig():
    """Example: Get job status without kubeconfig (in-cluster)."""
    print("\n4. Getting job status WITHOUT kubeconfig (in-cluster)...")
    
    job_id = "eval-123e4567-e89b-12d3-a456-426614174001"
    
    # No kubeconfig parameter - will use in-cluster config
    response = requests.get(f"{BASE_URL}/evals/status/{job_id}")
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


def example_cleanup_with_kubeconfig():
    """Example: Cleanup job with kubeconfig."""
    print("\n5. Cleaning up job WITH kubeconfig...")
    
    job_id = "eval-123e4567-e89b-12d3-a456-426614174000"
    kubeconfig = json.dumps({
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "my-cluster", "cluster": {"server": "https://k8s.example.com"}}],
        "contexts": [{"name": "my-context", "context": {"cluster": "my-cluster", "user": "my-user"}}],
        "current-context": "my-context",
        "users": [{"name": "my-user", "user": {"token": "my-token"}}]
    })
    
    response = requests.delete(f"{BASE_URL}/evals/cleanup/{job_id}", params={"kubeconfig": kubeconfig})
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


def example_cleanup_without_kubeconfig():
    """Example: Cleanup job without kubeconfig (in-cluster)."""
    print("\n6. Cleaning up job WITHOUT kubeconfig (in-cluster)...")
    
    job_id = "eval-123e4567-e89b-12d3-a456-426614174001"
    
    # No kubeconfig parameter - will use in-cluster config
    response = requests.delete(f"{BASE_URL}/evals/cleanup/{job_id}")
    print(f"Response: {response.status_code}")
    print(f"Body: {response.json()}")


if __name__ == "__main__":
    print("=" * 60)
    print("API Usage Examples - Optional Kubeconfig")
    print("=" * 60)
    print("\nNote: These are examples showing the API usage patterns.")
    print("Replace the BASE_URL and credentials with your actual values.")
    print("\nWhen running inside Kubernetes:")
    print("- Omit the kubeconfig parameter")
    print("- The service will use in-cluster authentication")
    print("\nWhen running outside Kubernetes:")
    print("- Provide the kubeconfig parameter")
    print("- The service will use the provided kubeconfig")
    print("=" * 60)