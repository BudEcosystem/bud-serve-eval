#!/usr/bin/env python3
"""
Test case for OpenCompass job execution with proper volume mounting.
Assumes:
- Dataset volume (eval-datasets-pvc) is already present and initialized
- Engines are preloaded
- ConfigMap creation works

This test will:
1. Create a test ConfigMap for OpenCompass
2. Submit a job with proper volume mounts
3. Monitor job execution until completion
4. Fetch and display logs
5. Check output artifacts
"""

import asyncio
import json
import time
import uuid
from datetime import datetime

from budeval.evals.configmap_manager import ConfigMapManager
from budeval.evals.services import EvaluationOpsService
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


class OpenCompassJobTest:
    def __init__(self):
        self.job_id = f"test-opencompass-{uuid.uuid4().hex[:8]}"
        self.eval_request_id = f"test-eval-{uuid.uuid4().hex[:8]}"
        self.orchestrator = AnsibleOrchestrator()
        self.configmap_manager = ConfigMapManager(namespace="budeval")

    async def setup_configmap(self):
        """Create OpenCompass ConfigMap for the test job."""
        print(f"📝 Creating ConfigMap for eval request: {self.eval_request_id}")

        try:
            result = self.configmap_manager.create_opencompass_config_map(
                eval_request_id=self.eval_request_id,
                model_name="test-model-gpt-3.5-turbo",
                api_key="test-api-key-12345",
                base_url="http://test-api.example.com/v1",
                datasets=["mmlu", "gsm8k"],
                max_out_len=1024,
                max_seq_len=2048,
                batch_size=4,
                temperature=0.0,
            )
            print(f"✅ ConfigMap created: {result['configmap_name']}")
            return result
        except Exception as e:
            print(f"❌ Failed to create ConfigMap: {e}")
            raise

    async def submit_job(self):
        """Submit OpenCompass evaluation job with proper volume mounting."""
        print(f"🚀 Submitting job: {self.job_id}")

        engine_args = {
            "eval_request_id": self.eval_request_id,
            "model_name": "test-model-gpt-3.5-turbo",
            "api_key": "test-api-key-12345",
            "base_url": "http://test-api.example.com/v1",
            "datasets": ["mmlu"],  # Use smaller dataset for testing
            "engine": "opencompass",
        }

        try:
            self.orchestrator.run_job_with_volumes(
                runner_type="kubernetes",
                uuid=self.job_id,
                kubeconfig=None,  # Use local k3s config
                engine_args=engine_args,
                docker_image="ghcr.io/rahulvramesh/opencompass:latest",
                namespace="budeval",
                ttl_seconds=1800,  # 30 minutes
                output_volume_size="5Gi",
            )
            print(f"✅ Job submitted successfully: {self.job_id}")
        except Exception as e:
            print(f"❌ Failed to submit job: {e}")
            raise

    async def monitor_job(self, timeout_minutes=30):
        """Monitor job execution until completion or timeout."""
        print(f"👀 Monitoring job: {self.job_id}")

        timeout_seconds = timeout_minutes * 60
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout_seconds:
            try:
                status = await EvaluationOpsService.get_job_status(self.job_id, None)
                current_status = status.get("status", "unknown")

                if current_status != last_status:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Job status: {current_status}")

                    # Print additional details
                    if "active" in status:
                        print(
                            f"  Active: {status['active']}, Succeeded: {status.get('succeeded', 0)}, Failed: {status.get('failed', 0)}"
                        )

                    last_status = current_status

                # Check terminal states
                if current_status in ["succeeded", "completed"]:
                    print(f"🎉 Job completed successfully!")
                    return "succeeded"
                elif current_status in ["failed", "error"]:
                    print(f"💥 Job failed!")
                    return "failed"

            except Exception as e:
                print(f"⚠️  Error checking job status: {e}")

            await asyncio.sleep(10)  # Check every 10 seconds

        print(f"⏰ Job monitoring timed out after {timeout_minutes} minutes")
        return "timeout"

    async def fetch_logs(self):
        """Fetch and display job logs."""
        print(f"📋 Fetching logs for job: {self.job_id}")

        import subprocess

        try:
            # Get pod name for the job
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    "budeval",
                    "-l",
                    f"job-name={self.job_id}",
                    "-o",
                    "jsonpath={.items[0].metadata.name}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                pod_name = result.stdout.strip()
                print(f"📦 Found pod: {pod_name}")

                # Fetch logs
                log_result = subprocess.run(
                    ["kubectl", "logs", pod_name, "-n", "budeval", "--tail=50"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if log_result.returncode == 0:
                    print(f"📋 Recent logs from {pod_name}:")
                    print("=" * 80)
                    print(log_result.stdout)
                    print("=" * 80)
                else:
                    print(f"❌ Failed to fetch logs: {log_result.stderr}")
            else:
                print(f"❌ Pod not found for job: {self.job_id}")

        except subprocess.TimeoutExpired:
            print("⏰ Timeout while fetching logs")
        except Exception as e:
            print(f"❌ Error fetching logs: {e}")

    async def check_outputs(self):
        """Check if outputs were generated in the output volume."""
        print(f"📂 Checking outputs for job: {self.job_id}")

        import subprocess

        try:
            # Create a temporary pod to check the output volume
            check_pod_name = f"output-check-{self.job_id}"

            # Run a pod to list contents of output volume
            result = subprocess.run(
                [
                    "kubectl",
                    "run",
                    check_pod_name,
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
                                        "name": check_pod_name,
                                        "image": "busybox",
                                        "command": [
                                            "sh",
                                            "-c",
                                            "echo 'Output volume contents:' && ls -la /workspace/outputs/ || echo 'Output volume empty or not mounted'",
                                        ],
                                        "volumeMounts": [{"name": "outputs", "mountPath": "/workspace/outputs"}],
                                    }
                                ],
                                "volumes": [
                                    {
                                        "name": "outputs",
                                        "persistentVolumeClaim": {"claimName": f"{self.job_id}-output-pvc"},
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

            if result.returncode == 0:
                print("📂 Output volume contents:")
                print(result.stdout)
            else:
                print(f"❌ Failed to check outputs: {result.stderr}")

        except subprocess.TimeoutExpired:
            print("⏰ Timeout while checking outputs")
        except Exception as e:
            print(f"❌ Error checking outputs: {e}")

    async def cleanup(self):
        """Clean up test resources."""
        print(f"🧹 Cleaning up resources for job: {self.job_id}")

        try:
            # Clean up job resources
            await EvaluationOpsService.cleanup_job(self.job_id, None)
            print(f"✅ Cleaned up job resources")
        except Exception as e:
            print(f"⚠️  Error during job cleanup: {e}")

        try:
            # Clean up ConfigMap
            success = self.configmap_manager.delete_opencompass_config_map(self.eval_request_id, None)
            if success:
                print(f"✅ Cleaned up ConfigMap")
            else:
                print(f"⚠️  Failed to clean up ConfigMap")
        except Exception as e:
            print(f"⚠️  Error during ConfigMap cleanup: {e}")

    async def run_full_test(self):
        """Run the complete test workflow."""
        print("🧪 Starting OpenCompass Job Execution Test")
        print("=" * 60)

        try:
            # Setup
            await self.setup_configmap()

            # Submit job
            await self.submit_job()

            # Monitor job
            final_status = await self.monitor_job(timeout_minutes=30)

            # Fetch logs regardless of final status
            await self.fetch_logs()

            # Check outputs if job succeeded
            if final_status == "succeeded":
                await self.check_outputs()

            print("=" * 60)
            print(f"🏁 Test completed with status: {final_status}")

            return final_status

        except Exception as e:
            print(f"💥 Test failed with error: {e}")
            return "error"
        finally:
            # Always try to cleanup
            await self.cleanup()


async def main():
    """Main test execution function."""
    print("🔬 OpenCompass Job Execution Test")
    print("📋 Prerequisites:")
    print("  - eval-datasets-pvc volume exists and is initialized")
    print("  - OpenCompass engine is preloaded")
    print("  - Kubernetes cluster is accessible")
    print("  - budeval namespace exists")
    print()

    test = OpenCompassJobTest()
    result = await test.run_full_test()

    if result == "succeeded":
        print("🎉 Test PASSED - Job completed successfully!")
        return 0
    elif result == "failed":
        print("💥 Test FAILED - Job execution failed!")
        return 1
    elif result == "timeout":
        print("⏰ Test TIMED OUT - Job did not complete in time!")
        return 2
    else:
        print("❌ Test ERROR - Unexpected error occurred!")
        return 3


if __name__ == "__main__":
    import sys

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
