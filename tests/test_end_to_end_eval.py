#!/usr/bin/env python3
"""
End-to-end evaluation test with ClickHouse integration.
"""

import asyncio
import json
import sys
import requests
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage, health_check_storage


async def test_end_to_end_evaluation():
    """Run end-to-end evaluation test with ClickHouse storage."""
    print("🚀 Starting end-to-end evaluation test with ClickHouse...")
    
    # Base URL for API (assuming app is running on port 8099)
    base_url = "http://localhost:8099"
    
    try:
        # First, verify ClickHouse storage is configured and working
        print("\n🔗 Testing ClickHouse storage configuration...")
        storage = get_storage_adapter()
        await initialize_storage(storage)
        
        health_result = await health_check_storage(storage)
        print(f"📊 Storage health: {health_result}")
        
        if not health_result.get("healthy"):
            print(f"❌ Storage not healthy: {health_result.get('error')}")
            return
        
        print("✅ ClickHouse storage is ready")
        
        # Check if the API is running
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code != 200:
                print("❌ API not running or not healthy")
                print("💡 Please start the app with: dapr run --run-file ./app.yaml")
                return
        except requests.exceptions.RequestException:
            print("❌ Cannot connect to API")
            print("💡 Please start the app with: dapr run --run-file ./app.yaml")
            return
            
        print("✅ API is running and healthy")
        
        # Prepare evaluation request (using proper schema)
        eval_request = {
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
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
        
        print(f"\n📝 Submitting evaluation request...")
        print(f"   Model: {eval_request['eval_model_info']['model_name']}")
        print(f"   Datasets: {[d['dataset_id'] for d in eval_request['eval_datasets']]}")
        print(f"   Job UUID: {eval_request['uuid']}")
        
        # Submit evaluation
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
        job_id = eval_request["uuid"]  # Use the UUID we sent as job_id
        
        if not workflow_id:
            print(f"❌ No workflow_id returned: {result}")
            return
            
        print(f"✅ Evaluation submitted successfully")
        print(f"📋 Job UUID: {job_id}")
        print(f"🔄 Workflow ID: {workflow_id}")
        print(f"📊 Status: {result.get('status')}")
        print(f"⏱️ ETA: {result.get('eta')} seconds")
        
        # Monitor evaluation progress
        print(f"\n⏳ Monitoring evaluation progress...")
        max_wait_time = 600  # 10 minutes
        check_interval = 10  # 10 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                # Try both workflow status and job status endpoints
                response = requests.get(f"{base_url}/evals/status/{job_id}", timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    
                    current_status = status.get('status', 'unknown')
                    print(f"📊 Status: {current_status} (elapsed: {int(time.time() - start_time)}s)")
                    
                    # Show workflow progress if available
                    if 'steps' in status:
                        for step in status.get('steps', []):
                            step_status = "✅" if step.get('completed') else "⏳"
                            print(f"    {step_status} {step.get('title', 'Unknown step')}")
                    
                    if current_status == "completed":
                        print("✅ Evaluation completed successfully!")
                        break
                    elif current_status == "failed":
                        print(f"❌ Evaluation failed: {status.get('error', 'Unknown error')}")
                        return
                    elif current_status in ["running", "pending"]:
                        pass  # Continue waiting
                    
                time.sleep(check_interval)
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Error checking status: {e}")
                time.sleep(check_interval)
        else:
            print(f"⏰ Evaluation timed out after {max_wait_time} seconds")
            return
        
        # Test data retrieval from ClickHouse
        print(f"\n🔍 Testing data retrieval from ClickHouse...")
        
        # Check if results exist in storage
        exists = await storage.exists(job_id)
        print(f"📊 Results exist in ClickHouse: {exists}")
        
        if exists:
            # Retrieve results
            results = await storage.get_results(job_id)
            if results:
                summary = results.get("summary", {})
                datasets = results.get("datasets", [])
                
                print(f"✅ Successfully retrieved results from ClickHouse:")
                print(f"   Job ID: {results.get('job_id')}")
                print(f"   Model: {summary.get('model_name', 'Unknown')}")
                print(f"   Engine: {results.get('engine', 'Unknown')}")
                print(f"   Overall Accuracy: {summary.get('overall_accuracy', 0):.4f}")
                print(f"   Total Datasets: {summary.get('total_datasets', 0)}")
                print(f"   Total Examples: {summary.get('total_examples', 0)}")
                print(f"   Total Correct: {summary.get('total_correct', 0)}")
                
                print(f"\n📋 Dataset Results:")
                for dataset in datasets:
                    print(f"   - {dataset.get('dataset_name')}: {dataset.get('accuracy', 0):.4f} accuracy")
                
                # Test prediction retrieval
                if datasets:
                    dataset_name = datasets[0].get('dataset_name')
                    predictions = await storage.get_predictions(job_id, dataset_name)
                    print(f"   - Predictions stored: {len(predictions)} examples")
                    
                    if predictions:
                        sample_pred = predictions[0]
                        print(f"   - Sample prediction: {sample_pred.get('example_abbr')} -> {sample_pred.get('is_correct')}")
            else:
                print("❌ Failed to retrieve results from ClickHouse")
        else:
            print("⚠️ Results not found in ClickHouse storage")
        
        # List all available results
        all_job_ids = await storage.list_results()
        print(f"\n📊 Total jobs in ClickHouse: {len(all_job_ids)}")
        for job in all_job_ids:
            print(f"   - {job}")
        
        await storage.close()
        print(f"\n✅ End-to-end evaluation test completed successfully!")
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_end_to_end_evaluation())