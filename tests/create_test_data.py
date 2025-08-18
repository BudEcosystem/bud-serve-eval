#!/usr/bin/env python3
"""
Create test evaluation data for migration testing.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def create_test_data():
    """Create sample evaluation results for testing migration."""
    print("🔧 Creating test evaluation data...")
    
    # Sample test results
    test_results = [
        {
            "job_id": "test-qwen2-math-001", 
            "model_name": "qwen2-math-7b",
            "engine": "opencompass",
            "job_start_time": datetime.now() - timedelta(hours=2),
            "job_end_time": datetime.now() - timedelta(hours=1),
            "job_duration_seconds": 3600.0,
            "extracted_at": datetime.now(),
            "summary": {
                "overall_accuracy": 0.825,
                "total_datasets": 2,
                "total_examples": 200,
                "total_correct": 165,
                "model_name": "qwen2-math-7b"
            },
            "datasets": [
                {
                    "dataset_name": "gsm8k",
                    "accuracy": 0.85,
                    "total_examples": 100,
                    "correct_examples": 85,
                    "metadata": {"version": "1.0", "type": "math"},
                    "predictions": [
                        {
                            "example_abbr": "gsm8k_001",
                            "prediction": "The answer is 42",
                            "origin_prompt": "What is 6 * 7?",
                            "pred": ["42"],
                            "answer": ["42"],
                            "correct": [True]
                        },
                        {
                            "example_abbr": "gsm8k_002", 
                            "prediction": "The answer is 15",
                            "origin_prompt": "What is 3 * 5?",
                            "pred": ["15"],
                            "answer": ["15"],
                            "correct": [True]
                        }
                    ]
                },
                {
                    "dataset_name": "math_qa",
                    "accuracy": 0.80,
                    "total_examples": 100,
                    "correct_examples": 80,
                    "metadata": {"version": "2.1", "type": "math"},
                    "predictions": [
                        {
                            "example_abbr": "math_qa_001",
                            "prediction": "The answer is 144",
                            "origin_prompt": "What is 12^2?",
                            "pred": ["144"],
                            "answer": ["144"],
                            "correct": [True]
                        }
                    ]
                }
            ]
        },
        {
            "job_id": "test-llama3-reasoning-002",
            "model_name": "llama3-8b-instruct", 
            "engine": "opencompass",
            "job_start_time": datetime.now() - timedelta(hours=4),
            "job_end_time": datetime.now() - timedelta(hours=3),
            "job_duration_seconds": 2400.0,
            "extracted_at": datetime.now(),
            "summary": {
                "overall_accuracy": 0.75,
                "total_datasets": 1,
                "total_examples": 150,
                "total_correct": 112,
                "model_name": "llama3-8b-instruct"
            },
            "datasets": [
                {
                    "dataset_name": "hellaswag",
                    "accuracy": 0.75,
                    "total_examples": 150,
                    "correct_examples": 112,
                    "metadata": {"version": "1.2", "type": "reasoning"},
                    "predictions": [
                        {
                            "example_abbr": "hellaswag_001",
                            "prediction": "Option A is correct",
                            "origin_prompt": "Choose the best completion...",
                            "pred": ["A"],
                            "answer": ["A"],
                            "correct": [True]
                        }
                    ]
                }
            ]
        }
    ]
    
    # Save to filesystem storage
    fs_storage = get_storage_adapter("filesystem")
    await initialize_storage(fs_storage)
    
    for result in test_results:
        success = await fs_storage.save_results(result["job_id"], result)
        if success:
            print(f"✅ Created test data for job: {result['job_id']}")
        else:
            print(f"❌ Failed to create test data for job: {result['job_id']}")
    
    print(f"🎯 Created {len(test_results)} test evaluation results")


if __name__ == "__main__":
    asyncio.run(create_test_data())