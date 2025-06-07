#!/usr/bin/env python3
"""Test script for ConfigMap creation functionality."""

import json
import requests

# Base URL of the evaluation service
BASE_URL = "http://localhost:8099"

def test_configmap_creation():
    """Test ConfigMap creation with OpenCompass model configuration."""
    print("Testing ConfigMap creation...")
    
    payload = {
        "eval_request_id": "test-123e4567-e89b-12d3-a456-426614174000",
        "model_name": "meta-llama/Llama-3.2-3B-Instruct",
        "api_key": "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",
        "base_url": "http://localhost:8988/v1/chat/completions",
        "datasets": ["mmlu", "gsm8k", "hellaswag"],
        "kubeconfig": None  # Will use local k3s.yaml
    }
    
    # Create ConfigMap
    response = requests.post(f"{BASE_URL}/evals/test-configmap", json=payload)
    print(f"Create ConfigMap Response: {response.status_code}")
    if response.status_code == 200:
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        # Get ConfigMap info
        eval_request_id = payload["eval_request_id"]
        info_response = requests.get(f"{BASE_URL}/evals/configmap/{eval_request_id}")
        print(f"\nGet ConfigMap Info Response: {info_response.status_code}")
        if info_response.status_code == 200:
            print(f"ConfigMap Info: {json.dumps(info_response.json(), indent=2)}")
        
        # Test full evaluation flow
        test_full_evaluation(payload)
        
    else:
        print(f"Error Body: {response.text}")

def test_full_evaluation(model_payload):
    """Test the full evaluation flow with ConfigMap creation."""
    print("\n" + "="*50)
    print("Testing full evaluation flow...")
    
    eval_payload = {
        "eval_request_id": model_payload["eval_request_id"],
        "model_name": model_payload["model_name"],
        "api_key": model_payload["api_key"],
        "base_url": model_payload["base_url"],
        "kubeconfig": None,  # Will use local k3s.yaml
        "source": "test_client",
        "source_topic": "test_topic"
    }
    
    response = requests.post(f"{BASE_URL}/evals/start", json=eval_payload)
    print(f"Start Evaluation Response: {response.status_code}")
    if response.status_code == 200:
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error Body: {response.text}")

def test_generated_config_content():
    """Test the generated configuration content."""
    print("\n" + "="*50)
    print("Testing generated configuration content...")
    
    from budeval.evals.config_generator import OpenCompassConfigGenerator
    
    # Test bud-model.py generation
    model_config = OpenCompassConfigGenerator.generate_bud_model_config(
        model_name="meta-llama/Llama-3.2-3B-Instruct",
        api_key="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",
        base_url="http://localhost:8988/v1/chat/completions",
        eval_request_id="test-123",
        max_out_len=2048,
        max_seq_len=4096,
        batch_size=8,
    )
    
    print("Generated bud-model.py content:")
    print("-" * 40)
    print(model_config)
    print("-" * 40)
    
    # Test dataset config generation
    dataset_config = OpenCompassConfigGenerator.generate_dataset_config(["mmlu", "gsm8k"])
    
    print("\nGenerated dataset config content:")
    print("-" * 40)
    print(dataset_config)
    print("-" * 40)

def cleanup_test_resources():
    """Clean up test resources."""
    print("\n" + "="*50)
    print("Cleaning up test resources...")
    
    eval_request_id = "test-123e4567-e89b-12d3-a456-426614174000"
    
    response = requests.delete(f"{BASE_URL}/evals/configmap/{eval_request_id}")
    print(f"Delete ConfigMap Response: {response.status_code}")
    if response.status_code == 200:
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error Body: {response.text}")

if __name__ == "__main__":
    print("🧪 Testing OpenCompass ConfigMap Creation")
    print("=" * 50)
    
    # Test configuration generation
    test_generated_config_content()
    
    # Test ConfigMap creation
    test_configmap_creation()
    
    # Cleanup
    cleanup_test_resources()
    
    print("\n✅ Tests completed!") 