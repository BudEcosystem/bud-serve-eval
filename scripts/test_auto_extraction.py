#!/usr/bin/env python3
"""
Test automatic extraction and ClickHouse integration for a completed job.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.results_processor import ResultsProcessor
from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def test_automatic_extraction():
    """Test automatic extraction for a completed job."""
    print("🧪 Testing automatic extraction and ClickHouse integration")
    print("=" * 80)
    
    # Use the completed job from our previous test
    job_id = "bf3742f1-97f9-4461-a061-8acd81f66352"
    model_name = "qwen3-4b"
    namespace = "budeval"
    
    print(f"📋 Job ID: {job_id}")
    print(f"🤖 Model: {model_name}")
    print(f"🏠 Namespace: {namespace}")
    
    try:
        # Initialize ClickHouse storage
        print("🔧 Initializing ClickHouse storage...")
        storage = get_storage_adapter("clickhouse")
        await initialize_storage(storage)
        
        # Create processor
        processor = ResultsProcessor(storage)
        
        # Test automatic extraction and processing
        print("🚀 Starting automatic extraction and processing...")
        results = await processor.extract_and_process(
            job_id=job_id,
            model_name=model_name,
            namespace=namespace,
            kubeconfig=None  # Uses in-cluster config
        )
        
        print("✅ Extraction and processing completed successfully!")
        print(f"📊 Results summary:")
        print(f"   Job ID: {results.job_id}")
        print(f"   Model: {results.model_name}")
        print(f"   Engine: {results.engine}")
        print(f"   Datasets: {len(results.datasets)}")
        print(f"   Overall Accuracy: {results.summary.overall_accuracy:.2%}")
        print(f"   Total Examples: {results.summary.total_examples}")
        print(f"   Total Correct: {results.summary.total_correct}")
        print(f"   Extracted At: {results.extracted_at}")
        
        # Verify data was saved to ClickHouse
        print("\n🔍 Verifying ClickHouse data...")
        async with storage.get_connection() as conn:
            async with conn.cursor() as cursor:
                # Check evaluation jobs
                await cursor.execute("SELECT COUNT(*) FROM budeval.evaluation_jobs WHERE job_id = %(job_id)s", {"job_id": job_id})
                job_count = await cursor.fetchone()
                print(f"📊 Evaluation jobs for {job_id}: {job_count[0]}")
                
                # Check dataset results
                await cursor.execute("SELECT COUNT(*) FROM budeval.dataset_results WHERE job_id = %(job_id)s", {"job_id": job_id})
                dataset_count = await cursor.fetchone()
                print(f"📊 Dataset results for {job_id}: {dataset_count[0]}")
                
                # Check predictions
                await cursor.execute("SELECT COUNT(*) FROM budeval.predictions WHERE job_id = %(job_id)s", {"job_id": job_id})
                pred_count = await cursor.fetchone()
                print(f"📊 Predictions for {job_id}: {pred_count[0]}")
                
                if job_count[0] > 0:
                    # Get job details
                    await cursor.execute("""
                        SELECT model_name, overall_accuracy, total_examples, total_correct, extracted_at
                        FROM budeval.evaluation_jobs 
                        WHERE job_id = %(job_id)s
                    """, {"job_id": job_id})
                    job_info = await cursor.fetchone()
                    if job_info:
                        print(f"📈 ClickHouse job data: {job_info[0]} - {job_info[1]:.2%} accuracy ({job_info[3]}/{job_info[2]}) - extracted at {job_info[4]}")
        
        await storage.close()
        
        # Final validation
        success = (
            results.summary.overall_accuracy > 0 and
            len(results.datasets) > 0 and
            results.summary.total_examples > 0
        )
        
        print("=" * 80)
        print(f"🏆 Automatic extraction test: {'✅ PASSED' if success else '❌ FAILED'}")
        
        if success:
            print("🎉 Automatic extraction and ClickHouse integration working perfectly!")
            print("💡 This demonstrates the complete automated workflow for results processing")
        else:
            print("💔 Test failed - check logs for details")
        
        return success
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_automatic_extraction())
    sys.exit(0 if success else 1)