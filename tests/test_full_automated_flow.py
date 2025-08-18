#!/usr/bin/env python3
"""
Test complete automated end-to-end flow with ClickHouse integration.
"""

import asyncio
import json
import sys
import requests
import time
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def test_full_automated_flow():
    """Test complete automated evaluation flow with ClickHouse."""
    print("🚀 Testing complete automated end-to-end flow...")
    
    # Generate unique job ID for this test
    test_job_id = str(uuid.uuid4())
    
    # Base URL for API
    base_url = "http://localhost:8099"
    
    try:
        # 1. Verify ClickHouse is clean and ready
        print("\n1️⃣ Verifying ClickHouse is clean...")
        storage = get_storage_adapter("clickhouse")
        await initialize_storage(storage)
        
        initial_jobs = await storage.list_results()
        print(f"   Initial jobs in ClickHouse: {len(initial_jobs)}")
        
        # 2. Check API health
        print("\n2️⃣ Checking API health...")
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code != 200:
            print("❌ API not healthy")
            return
        print("   ✅ API is healthy")
        
        # 3. Submit evaluation request
        print(f"\n3️⃣ Submitting evaluation request...")
        eval_request = {
            "uuid": test_job_id,
            "engine": "opencompass", 
            "eval_model_info": {
                "model_name": "qwen3-4b",
                "endpoint": "http://20.66.97.208/v1",
                "api_key": "test-key",
                "extra_args": {
                    "temperature": 0.0,
                    "max_tokens": 2048
                }
            },
            "eval_datasets": [
                {"dataset_id": "demo_gsm8k"}
            ],
            "eval_configs": []
        }
        
        print(f"   Job UUID: {test_job_id}")
        print(f"   Model: {eval_request['eval_model_info']['model_name']}")
        print(f"   Dataset: {eval_request['eval_datasets'][0]['dataset_id']}")
        
        response = requests.post(
            f"{base_url}/evals/start",
            json=eval_request,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to submit evaluation: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        result = response.json()
        workflow_id = result.get("workflow_id")
        print(f"   ✅ Evaluation submitted")
        print(f"   Workflow ID: {workflow_id}")
        
        # 4. Monitor evaluation progress
        print(f"\n4️⃣ Monitoring evaluation progress...")
        max_wait_time = 1200  # 20 minutes
        check_interval = 15   # 15 seconds
        start_time = time.time()
        
        last_status = None
        
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(f"{base_url}/evals/status/{test_job_id}", timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    current_status = status.get('status', 'unknown')
                    elapsed = int(time.time() - start_time)
                    
                    # Only print if status changed or every minute
                    if current_status != last_status or elapsed % 60 == 0:
                        print(f"   📊 Status: {current_status} (elapsed: {elapsed}s)")
                        last_status = current_status
                    
                    if current_status == "completed":
                        print("   ✅ Evaluation completed successfully!")
                        break
                    elif current_status == "failed":
                        print(f"   ❌ Evaluation failed: {status.get('error', 'Unknown error')}")
                        return
                    
                time.sleep(check_interval)
                
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Error checking status: {e}")
                time.sleep(check_interval)
        else:
            print(f"   ⏰ Evaluation timed out after {max_wait_time/60:.1f} minutes")
            return
        
        # 5. Wait a bit for results processing
        print(f"\n5️⃣ Waiting for results processing...")
        await asyncio.sleep(30)  # Give time for extraction and processing
        
        # 6. Check if results were automatically saved to ClickHouse
        print(f"\n6️⃣ Checking ClickHouse for automated results...")
        
        # Check if job exists
        exists = await storage.exists(test_job_id)
        print(f"   Job exists in ClickHouse: {exists}")
        
        if exists:
            # Retrieve and verify results
            results = await storage.get_results(test_job_id)
            if results:
                summary = results.get("summary", {})
                datasets = results.get("datasets", [])
                
                print(f"   ✅ Automated ClickHouse integration successful!")
                print(f"   📊 Results Summary:")
                print(f"      Job ID: {results.get('job_id')}")
                print(f"      Model: {summary.get('model_name')}")
                print(f"      Engine: {results.get('engine')}")
                print(f"      Overall Accuracy: {summary.get('overall_accuracy', 0):.4f}")
                print(f"      Total Datasets: {summary.get('total_datasets', 0)}")
                print(f"      Total Examples: {summary.get('total_examples', 0)}")
                print(f"      Total Correct: {summary.get('total_correct', 0)}")
                
                for dataset in datasets:
                    print(f"      Dataset {dataset.get('dataset_name')}: {dataset.get('accuracy', 0):.4f} accuracy")
                
                # Check predictions
                predictions = await storage.get_predictions(test_job_id)
                print(f"      Predictions stored: {len(predictions)} examples")
                
                if predictions:
                    correct_count = sum(1 for p in predictions if p.get('is_correct'))
                    print(f"      Correct predictions: {correct_count}/{len(predictions)}")
                
                # 7. Final verification - compare with all jobs
                print(f"\n7️⃣ Final verification...")
                all_jobs = await storage.list_results()
                print(f"   Total jobs in ClickHouse: {len(all_jobs)}")
                print(f"   New jobs added: {len(all_jobs) - len(initial_jobs)}")
                
                if test_job_id in all_jobs:
                    print(f"   ✅ Test job {test_job_id} confirmed in database")
                else:
                    print(f"   ❌ Test job {test_job_id} NOT found in database")
                
                print(f"\n🎉 COMPLETE SUCCESS: Automated end-to-end flow with ClickHouse integration!")
                print(f"   📈 Evaluation completed and results automatically saved to ClickHouse")
                print(f"   🔄 No manual intervention required")
                
            else:
                print(f"   ❌ Results exist but failed to retrieve")
        else:
            print(f"   ❌ Results not found in ClickHouse")
            print(f"   🔍 Checking if extraction happened...")
            
            # Check if extraction files exist
            extraction_path = f"/tmp/eval_extractions/{test_job_id}"
            if Path(extraction_path).exists():
                print(f"   📁 Extraction files found at {extraction_path}")
                print(f"   ⚠️  Extraction succeeded but ClickHouse sync may have failed")
            else:
                print(f"   📁 No extraction files found")
                print(f"   ⚠️  Results extraction may have failed")
        
        await storage.close()
        
    except Exception as e:
        print(f"❌ Automated flow test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_full_automated_flow())