#!/usr/bin/env python3
"""
Complete end-to-end test of the updated OpenCompass integration with config file approach.
"""

import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime

from budeval.evals.configmap_manager import ConfigMapManager
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


async def test_complete_integration():
    """Test the complete OpenCompass integration with updated config approach."""
    
    job_id = f"test-config-{uuid.uuid4().hex[:8]}"
    eval_request_id = f"test-llama-{uuid.uuid4().hex[:8]}"
    
    print("🧪 Complete OpenCompass Integration Test with Config File Approach")
    print("=" * 70)
    print(f"📋 Job ID: {job_id}")
    print(f"📋 Eval Request ID: {eval_request_id}")
    
    # Test parameters matching real-world usage
    test_params = {
        "eval_request_id": eval_request_id,
        "model_name": "meta-llama/Llama-3.2-3B-Instruct",
        "api_key": "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",
        "base_url": "http://localhost:8988/v1/chat/completions",
        "datasets": ["mmlu"],
        "kubeconfig": None,  # Use local k3s config
        "max_out_len": 2048,
        "max_seq_len": 4096,
        "batch_size": 8,
        "query_per_second": 1
    }
    
    print(f"📋 Test Parameters:")
    for key, value in test_params.items():
        if key == "api_key":
            print(f"  {key}: {value[:20]}...")
        elif key == "kubeconfig":
            print(f"  {key}: Using local k3s.yaml")
        else:
            print(f"  {key}: {value}")
    
    try:
        # Step 1: Create ConfigMap
        print(f"\n1️⃣ Creating ConfigMap...")
        configmap_manager = ConfigMapManager(namespace="budeval")
        
        configmap_result = configmap_manager.create_opencompass_config_map(
            eval_request_id=test_params["eval_request_id"],
            model_name=test_params["model_name"],
            api_key=test_params["api_key"],
            base_url=test_params["base_url"],
            datasets=test_params["datasets"],
            kubeconfig=test_params["kubeconfig"],
            max_out_len=test_params["max_out_len"],
            max_seq_len=test_params["max_seq_len"],
            batch_size=test_params["batch_size"],
            query_per_second=test_params["query_per_second"]
        )
        
        print(f"✅ ConfigMap created: {configmap_result['configmap_name']}")
        print(f"   Files: {', '.join(configmap_result['files'])}")
        print(f"   Action: {configmap_result['action']}")
        
        # Step 2: Create Job with Volumes
        print(f"\n2️⃣ Creating Job with Volumes...")
        orchestrator = AnsibleOrchestrator()
        
        # Create engine args for job
        engine_args = {
            "eval_request_id": test_params["eval_request_id"],
            "model_name": test_params["model_name"],
            "api_key": test_params["api_key"],
            "base_url": test_params["base_url"],
            "datasets": test_params["datasets"]
        }
        
        # Deploy the job
        orchestrator.run_job_with_volumes(
            runner_type="kubernetes",
            uuid=job_id,
            kubeconfig=test_params["kubeconfig"],
            engine_args=engine_args,
            docker_image="ghcr.io/rahulvramesh/opencompass:latest",
            namespace="budeval",
            ttl_seconds=600,
            output_volume_size="5Gi"
        )
        
        print(f"✅ Job {job_id} deployed successfully")
        
        # Step 3: Monitor Job
        print(f"\n3️⃣ Monitoring Job Progress...")
        max_attempts = 120  # 10 minutes
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                job_status = orchestrator.get_job_status(
                    uuid=job_id,
                    kubeconfig=test_params["kubeconfig"],
                    namespace="budeval"
                )
                
                status = job_status.get("status", "unknown")
                phase = job_status.get("phase", "unknown")
                active = job_status.get("active", 0)
                succeeded = job_status.get("succeeded", 0)
                failed = job_status.get("failed", 0)
                
                print(f"  📊 Attempt {attempt}: Status={status}, Phase={phase}, Active={active}, Succeeded={succeeded}, Failed={failed}")
                
                if succeeded > 0:
                    print(f"🎉 Job {job_id} completed successfully!")
                    break
                elif failed > 0:
                    print(f"💥 Job {job_id} failed!")
                    break
                elif attempt % 10 == 0:
                    print(f"  ⏳ Still running... ({attempt}/{max_attempts})")
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"  ⚠️  Error checking status: {e}")
                await asyncio.sleep(5)
        
        if attempt >= max_attempts:
            print(f"⏰ Job monitoring timed out after {max_attempts} attempts")
        
        # Step 4: Check logs for verification
        print(f"\n4️⃣ Checking Job Logs...")
        try:
            log_result = subprocess.run([
                "kubectl", "logs", "-n", "budeval", f"job/{job_id}", "--tail=50"
            ], capture_output=True, text=True, timeout=30)
            
            if log_result.returncode == 0:
                logs = log_result.stdout
                print("📋 Recent Job Logs:")
                print("-" * 40)
                print(logs[-1000:])  # Last 1000 chars
                print("-" * 40)
                
                # Check for key indicators in logs
                indicators = [
                    "bud-model",
                    "mmlu_gen", 
                    "--models",
                    "--datasets",
                    "--debug",
                    "/workspace/configs",
                    "/workspace/outputs"
                ]
                
                print("\n🔍 Checking for key indicators in logs:")
                for indicator in indicators:
                    if indicator in logs:
                        print(f"  ✅ Found: {indicator}")
                    else:
                        print(f"  ❌ Missing: {indicator}")
                        
            else:
                print(f"⚠️  Could not retrieve logs: {log_result.stderr}")
                
        except Exception as e:
            print(f"⚠️  Error retrieving logs: {e}")
        
        # Step 5: Check output volume
        print(f"\n5️⃣ Checking Output Volume...")
        try:
            # Create a temporary pod to check outputs
            output_check_result = subprocess.run([
                "kubectl", "run", f"output-check-{job_id[:8]}", "--rm", "-i", "--restart=Never",
                "--image=busybox", "-n", "budeval",
                "--overrides", json.dumps({
                    "spec": {
                        "containers": [{
                            "name": f"output-check-{job_id[:8]}",
                            "image": "busybox",
                            "command": ["sh", "-c", "ls -la /outputs/ | head -20"],
                            "volumeMounts": [{
                                "name": "output-volume",
                                "mountPath": "/outputs"
                            }]
                        }],
                        "volumes": [{
                            "name": "output-volume",
                            "persistentVolumeClaim": {
                                "claimName": f"{job_id}-output-pvc"
                            }
                        }]
                    }
                }),
                "--", "sh"
            ], capture_output=True, text=True, timeout=60)
            
            if output_check_result.returncode == 0:
                print("📂 Output Volume Contents:")
                print(output_check_result.stdout)
            else:
                print(f"⚠️  Could not check output volume: {output_check_result.stderr}")
                
        except Exception as e:
            print(f"⚠️  Error checking output volume: {e}")
        
        print(f"\n✅ Integration test completed for job {job_id}")
        print(f"🧹 Remember to clean up resources if needed")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run complete integration test."""
    print(f"🕒 Starting test at {datetime.now().isoformat()}")
    success = await test_complete_integration()
    print(f"🕒 Test completed at {datetime.now().isoformat()}")
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)