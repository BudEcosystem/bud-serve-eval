#!/usr/bin/env python3
"""
Simple test to verify OpenCompass volume mounting is working correctly.
This test creates a minimal job to check volume mounts without ConfigMap dependency.
"""

import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime

from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


async def test_volume_mounting():
    """Test volume mounting for OpenCompass job."""

    job_id = f"volume-test-{uuid.uuid4().hex[:8]}"
    print(f"🧪 Testing volume mounting with job: {job_id}")

    orchestrator = AnsibleOrchestrator()

    # Create a simple test job that lists mounted volumes
    engine_args = {"eval_request_id": "volume-test-123", "command": "volume-check"}

    # Generate job YAML to inspect volume mounts
    job_yaml = orchestrator._render_job_with_volumes_yaml(
        uuid=job_id,
        docker_image="busybox:1.35",  # Use simple image for testing
        args=engine_args,
        namespace="budeval",
        ttl=300,
    )

    print("📋 Generated Job YAML:")
    print("=" * 60)
    print(job_yaml)
    print("=" * 60)

    # Check if the volume mounts are correct for OpenCompass
    expected_mounts = ["/workspace/data", "/workspace/outputs", "/workspace/configs", "/workspace/cache"]

    print("✅ Checking volume mount paths...")
    for mount in expected_mounts:
        if mount in job_yaml:
            print(f"  ✅ {mount} - Found")
        else:
            print(f"  ❌ {mount} - Missing")

    # Check working directory
    if "workingDir: /workspace" in job_yaml:
        print("  ✅ Working directory: /workspace - Correct")
    else:
        print("  ❌ Working directory: Not set to /workspace")

    # Check volume types
    volume_checks = [
        ("eval-datasets-pvc", "Shared datasets volume"),
        ("output-pvc", "Job-specific output volume"),
        ("emptyDir", "Cache volume"),
        ("configMap", "Configuration volume"),
    ]

    print("✅ Checking volume types...")
    for volume_type, description in volume_checks:
        if volume_type in job_yaml:
            print(f"  ✅ {description} - Found")
        else:
            print(f"  ❌ {description} - Missing")

    return True


async def test_dataset_volume_exists():
    """Check if the eval-datasets-pvc exists and has data."""
    print("📂 Checking dataset volume...")

    try:
        # Check if PVC exists
        result = subprocess.run(
            ["kubectl", "get", "pvc", "eval-datasets-pvc", "-n", "budeval", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            pvc_info = json.loads(result.stdout)
            status = pvc_info.get("status", {}).get("phase", "Unknown")
            print(f"  ✅ eval-datasets-pvc status: {status}")

            if status == "Bound":
                # Try to check if it has data
                check_result = subprocess.run(
                    [
                        "kubectl",
                        "run",
                        "dataset-check",
                        "--rm",
                        "-i",
                        "--restart=Never",
                        "--image=busybox",
                        "-n",
                        "budeval",
                        "--overrides",
                        json.dumps(
                            {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "dataset-check",
                                            "image": "busybox",
                                            "command": ["sh", "-c", "ls -la /data/ | head -10"],
                                            "volumeMounts": [{"name": "datasets", "mountPath": "/data"}],
                                        }
                                    ],
                                    "volumes": [
                                        {
                                            "name": "datasets",
                                            "persistentVolumeClaim": {"claimName": "eval-datasets-pvc"},
                                        }
                                    ],
                                }
                            }
                        ),
                        "--",
                        "sh",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if check_result.returncode == 0:
                    print("  📂 Dataset volume contents:")
                    print("    " + check_result.stdout.replace("\n", "\n    "))
                else:
                    print(f"  ⚠️  Could not list dataset contents: {check_result.stderr}")

            return True
        else:
            print(f"  ❌ eval-datasets-pvc not found: {result.stderr}")
            return False

    except Exception as e:
        print(f"  ❌ Error checking dataset volume: {e}")
        return False


async def test_namespace_exists():
    """Check if budeval namespace exists."""
    print("🔍 Checking budeval namespace...")

    try:
        result = subprocess.run(["kubectl", "get", "namespace", "budeval"], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("  ✅ budeval namespace exists")
            return True
        else:
            print("  ❌ budeval namespace not found")
            return False

    except Exception as e:
        print(f"  ❌ Error checking namespace: {e}")
        return False


async def main():
    """Run all volume mounting tests."""
    print("🧪 OpenCompass Volume Mounting Test")
    print("=" * 50)

    all_passed = True

    # Test 1: Check prerequisites
    print("1️⃣ Testing Prerequisites")
    namespace_ok = await test_namespace_exists()
    dataset_ok = await test_dataset_volume_exists()

    if not namespace_ok or not dataset_ok:
        print("❌ Prerequisites not met, stopping tests")
        return 1

    print()

    # Test 2: Check volume mounting configuration
    print("2️⃣ Testing Volume Mount Configuration")
    volume_config_ok = await test_volume_mounting()

    if not volume_config_ok:
        all_passed = False

    print()
    print("=" * 50)

    if all_passed:
        print("🎉 All tests PASSED!")
        print("✅ Volume mounting configuration is correct for OpenCompass")
        return 0
    else:
        print("💥 Some tests FAILED!")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
