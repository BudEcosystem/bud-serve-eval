#!/usr/bin/env python3
"""
End-to-end evaluation test with ClickHouse integration.
"""

import asyncio
import json
import time
import sys
import uuid
from pathlib import Path
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


def test_api_endpoint():
    """Test the API endpoint first."""
    try:
        response = requests.get("http://localhost:8099/health")
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API not reachable: {e}")
        return False


def submit_evaluation():
    """Submit evaluation request."""
    print("🚀 Submitting evaluation request...")
    
    payload = {
        "uuid": str(uuid.uuid4()),
        "eval_model_info": {
            "model_name": "qwen3-4b",
            "endpoint": "http://20.66.97.208/v1/chat/completions",
            "api_key": "sk-test-key"
        },
        "eval_datasets": [
            {
                "dataset_id": "demo_gsm8k",
                "version": "1.0",
                "metadata": {}
            }
        ],
        "engine": "opencompass",
        "kubeconfig": "",
        "source": "test",
        "source_topic": "eval-responses"
    }

    
    try:
        response = requests.post(
            "http://localhost:8099/evals/start",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 202:
            result = response.json()
            print(f"✅ Evaluation started: {result}")
            return result.get("param", {}).get("workflow_id")
        else:
            print(f"❌ Failed to start evaluation: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error submitting evaluation: {e}")
        return None


def monitor_evaluation(workflow_id):
    """Monitor evaluation progress."""
    print(f"📊 Monitoring evaluation {workflow_id}...")
    
    max_attempts = 120  # 10 minutes
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"http://localhost:8099/evals/status/{workflow_id}")
            
            if response.status_code == 200:
                status = response.json()
                print(f"📈 Attempt {attempt + 1}: {status.get('status', 'unknown')}")
                
                # Check if completed
                if status.get("status") in ["completed", "succeeded", "failed"]:
                    print(f"🏁 Evaluation completed with status: {status.get('status')}")
                    return status
                    
                # Check specific workflow details
                details = status.get("details", {})
                if details.get("status") in ["completed", "succeeded", "failed"]:
                    print(f"🏁 Workflow completed with status: {details.get('status')}")
                    return status
            else:
                print(f"⚠️  Status check failed: {response.status_code}")
            
            time.sleep(5)  # Wait 5 seconds between checks
            
        except Exception as e:
            print(f"⚠️  Error checking status: {e}")
            time.sleep(5)
    
    print("⏰ Monitoring timed out")
    return None


async def verify_clickhouse_data():
    """Verify data was saved to ClickHouse."""
    print("🔍 Verifying ClickHouse data...")
    
    try:
        storage = get_storage_adapter("clickhouse")
        await initialize_storage(storage)
        
        # Get connection and check data
        async with storage.get_connection() as conn:
            async with conn.cursor() as cursor:
                # Check evaluation jobs
                await cursor.execute("SELECT COUNT(*) FROM budeval.evaluation_jobs")
                job_count = await cursor.fetchone()
                print(f"📊 Evaluation jobs: {job_count[0]}")
                
                # Check dataset results
                await cursor.execute("SELECT COUNT(*) FROM budeval.dataset_results")
                dataset_count = await cursor.fetchone()
                print(f"📊 Dataset results: {dataset_count[0]}")
                
                # Check predictions
                await cursor.execute("SELECT COUNT(*) FROM budeval.predictions")
                pred_count = await cursor.fetchone()
                print(f"📊 Predictions: {pred_count[0]}")
                
                if job_count[0] > 0:
                    # Get job details
                    await cursor.execute("""
                        SELECT job_id, model_name, overall_accuracy, total_examples, total_correct
                        FROM budeval.evaluation_jobs 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """)
                    job_info = await cursor.fetchone()
                    if job_info:
                        print(f"📈 Latest job: {job_info[0]} - {job_info[1]} - {job_info[2]:.2%} accuracy ({job_info[4]}/{job_info[3]})")
                
                success = job_count[0] > 0 and dataset_count[0] > 0 and pred_count[0] > 0
                print(f"{'✅' if success else '❌'} ClickHouse verification: {'PASSED' if success else 'FAILED'}")
                
        await storage.close()
        return success
        
    except Exception as e:
        print(f"❌ ClickHouse verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run end-to-end test."""
    print("🧪 Starting end-to-end evaluation test with ClickHouse integration")
    print("=" * 80)
    
    # 1. Check API availability
    if not test_api_endpoint():
        print("❌ Test failed: API not available")
        return False
    
    # 2. Submit evaluation
    workflow_id = submit_evaluation()
    if not workflow_id:
        print("❌ Test failed: Could not submit evaluation")
        return False
    
    # 3. Monitor progress
    final_status = monitor_evaluation(workflow_id)
    if not final_status:
        print("❌ Test failed: Monitoring timed out")
        return False
    
    # 4. Wait a bit for results processing
    print("⏳ Waiting for results processing...")
    await asyncio.sleep(30)
    
    # 5. Verify ClickHouse data
    clickhouse_ok = await verify_clickhouse_data()
    
    # Final result
    success = clickhouse_ok and final_status.get("status") in ["completed", "succeeded"]
    print("=" * 80)
    print(f"🏆 End-to-end test: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        print("🎉 Complete automated workflow with ClickHouse integration working!")
    else:
        print("💔 Test failed - check logs for details")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
