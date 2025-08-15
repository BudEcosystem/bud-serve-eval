#!/usr/bin/env python3
"""End-to-end test for evaluation API with debugging."""

import json
import subprocess
import time
import uuid

import requests


def test_evaluation_api():
    """Test the evaluation API end-to-end."""
    # Generate dynamic eval_request_id
    eval_request_id = str(uuid.uuid4())

    # API endpoint
    base_url = "http://localhost:8099"

    # Test payload with gsm8k dataset
    payload = {
        "eval_request_id": eval_request_id,
        "engine": "opencompass",
        "model_name": "qwen3-4b",  # Using the working model from CLAUDE.md
        "api_key": "sk-dummy-key",  # OpenCompass doesn't validate this for open endpoints
        "base_url": "http://20.66.97.208/v1",  # Using the working endpoint from CLAUDE.md
        "datasets": ["gsm8k"],
    }

    print("=== Starting Evaluation Test ===")
    print(f"Eval Request ID: {eval_request_id}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    # Step 1: Submit evaluation request
    print("\n--- Step 1: Submitting evaluation request ---")
    try:
        response = requests.post(f"{base_url}/evals/start", json=payload)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")

        if response.status_code != 200:
            print("ERROR: Failed to submit evaluation request")
            return False

        workflow_id = response.json().get("workflow_id")
        print(f"Workflow ID: {workflow_id}")

    except Exception as e:
        print(f"ERROR: Failed to submit request - {e}")
        return False

    # Step 2: Wait a bit for job to be created
    print("\n--- Step 2: Waiting for job creation ---")
    time.sleep(10)

    # Step 3: Check Kubernetes job status
    print("\n--- Step 3: Checking Kubernetes job status ---")
    job_name = f"eval-{eval_request_id}"

    # Check if job exists
    try:
        result = subprocess.run(
            ["kubectl", "get", "job", job_name, "-n", "budeval", "-o", "json"], capture_output=True, text=True
        )

        if result.returncode == 0:
            job_info = json.loads(result.stdout)
            print(f"Job found: {job_name}")
            print(f"Job status: {json.dumps(job_info.get('status', {}), indent=2)}")

            # Check job spec for command details
            spec = job_info.get("spec", {}).get("template", {}).get("spec", {})
            containers = spec.get("containers", [])
            if containers:
                container = containers[0]
                print(f"\nContainer Image: {container.get('image')}")
                print(f"Command: {container.get('command')}")
                args = container.get("args", [])
                if args and len(args) > 0:
                    print("Script Preview (first 500 chars):")
                    print(args[0][:500])
        else:
            print(f"Job not found: {job_name}")
            print(f"stderr: {result.stderr}")

    except Exception as e:
        print(f"ERROR: Failed to check job status - {e}")

    # Step 4: Check pod logs
    print("\n--- Step 4: Checking pod logs ---")
    try:
        # Get pods for this job
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "budeval", "-l", f"job-name={job_name}", "-o", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            pods_info = json.loads(result.stdout)
            pods = pods_info.get("items", [])

            if pods:
                pod_name = pods[0]["metadata"]["name"]
                print(f"Found pod: {pod_name}")
                print(f"Pod status: {pods[0]['status']['phase']}")

                # Get pod logs
                log_result = subprocess.run(
                    ["kubectl", "logs", pod_name, "-n", "budeval", "--tail=100"], capture_output=True, text=True
                )

                if log_result.returncode == 0:
                    print("\nPod logs (last 100 lines):")
                    print(log_result.stdout)
                else:
                    print(f"Failed to get logs: {log_result.stderr}")
            else:
                print("No pods found for the job")

    except Exception as e:
        print(f"ERROR: Failed to check pod logs - {e}")

    # Step 5: Check ConfigMap
    print("\n--- Step 5: Checking ConfigMap ---")
    configmap_name = f"opencompass-config-{eval_request_id.lower()}"
    try:
        result = subprocess.run(
            ["kubectl", "get", "configmap", configmap_name, "-n", "budeval", "-o", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            cm_info = json.loads(result.stdout)
            print(f"ConfigMap found: {configmap_name}")
            data = cm_info.get("data", {})
            print(f"ConfigMap keys: {list(data.keys())}")

            # Show model config if present
            if "bud-model.py" in data:
                print("\nbud-model.py content:")
                print(data["bud-model.py"])
        else:
            print(f"ConfigMap not found: {configmap_name}")

    except Exception as e:
        print(f"ERROR: Failed to check ConfigMap - {e}")

    # Step 6: Check API status endpoint
    print("\n--- Step 6: Checking API status endpoint ---")
    try:
        response = requests.get(f"{base_url}/evals/status/{job_name}")
        print(f"Status Response: {response.status_code}")
        if response.status_code == 200:
            print(f"Status Body: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"ERROR: Failed to check status - {e}")

    # Cleanup debug pod if exists
    subprocess.run(
        ["kubectl", "delete", "pod", "-n", "budeval", "dataset-debug-pod"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return True


if __name__ == "__main__":
    test_evaluation_api()
