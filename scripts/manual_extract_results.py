#!/usr/bin/env python3
"""
Manually extract and process evaluation results to test ClickHouse integration.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.results_processor import ResultsProcessor


async def manual_extract_results():
    """Manually extract and process results for testing."""
    print("🔧 Manually extracting evaluation results...")
    
    try:
        job_id = "bf3742f1-97f9-4461-a061-8acd81f66352"
        processor = ResultsProcessor()
        
        print(f"📋 Processing results for job: {job_id}")
        
        # Extract and process the completed evaluation
        result = await processor.extract_and_process(job_id, model_name="qwen3-4b")
        
        if result:
            print("✅ Results processed successfully!")
            print(f"📊 Result: {result}")
        else:
            print("❌ Failed to process results")
        
    except Exception as e:
        print(f"❌ Manual extraction failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(manual_extract_results())