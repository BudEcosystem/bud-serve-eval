#!/usr/bin/env python3
"""
Process extracted evaluation results and save to ClickHouse.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def process_extracted_results():
    """Process extracted results and save to ClickHouse."""
    print("🔧 Processing extracted evaluation results...")
    
    try:
        job_id = "bf3742f1-97f9-4461-a061-8acd81f66352"
        model_name = "qwen3-4b"
        
        # Path to extracted results
        base_path = f"/tmp/eval_extractions/{job_id}/outputs/20250818_042834"
        
        print(f"📂 Reading results from: {base_path}")
        
        # Read the results JSON
        results_file = f"{base_path}/results/{model_name}/demo_gsm8k.json"
        with open(results_file, 'r') as f:
            dataset_results = json.load(f)
        
        print(f"📊 Dataset accuracy: {dataset_results['accuracy']:.4f}")
        print(f"📋 Total examples: {len(dataset_results['details'])}")
        
        # Read predictions
        predictions_file = f"{base_path}/predictions/{model_name}/demo_gsm8k.json"
        with open(predictions_file, 'r') as f:
            predictions_data = json.load(f)
        
        # Build comprehensive results structure
        results = {
            "job_id": job_id,
            "model_name": model_name,
            "engine": "opencompass",
            "job_start_time": datetime.now(),
            "job_end_time": datetime.now(),
            "job_duration_seconds": 900.0,  # Approximate from our monitoring
            "extracted_at": datetime.now(),
            "summary": {
                "overall_accuracy": dataset_results["accuracy"] / 100.0,  # Convert to decimal
                "total_datasets": 1,
                "total_examples": len(dataset_results["details"]),
                "total_correct": sum(1 for detail in dataset_results["details"] if detail["correct"][0]),
                "model_name": model_name
            },
            "datasets": [
                {
                    "dataset_name": "demo_gsm8k",
                    "accuracy": dataset_results["accuracy"] / 100.0,  # Convert to decimal
                    "total_examples": len(dataset_results["details"]),
                    "correct_examples": sum(1 for detail in dataset_results["details"] if detail["correct"][0]),
                    "metadata": {"version": "1d7fe4", "type": "math"},
                    "predictions": []
                }
            ]
        }
        
        # Add predictions to the dataset
        for i, (detail, pred_data) in enumerate(zip(dataset_results["details"], predictions_data.values())):
            prediction = {
                "example_abbr": detail["example_abbr"],
                "prediction": pred_data.get("prediction", ""),
                "origin_prompt": pred_data.get("origin_prompt", ""),
                "pred": detail["pred"],
                "answer": detail["answer"],
                "correct": detail["correct"]
            }
            results["datasets"][0]["predictions"].append(prediction)
        
        print(f"✅ Processed {len(results['datasets'][0]['predictions'])} predictions")
        
        # Save to ClickHouse
        print(f"💾 Saving to ClickHouse...")
        storage = get_storage_adapter("clickhouse")
        await initialize_storage(storage)
        
        success = await storage.save_results(job_id, results)
        
        if success:
            print(f"✅ Successfully saved results to ClickHouse!")
            
            # Verify the save
            print(f"🔍 Verifying saved data...")
            retrieved_results = await storage.get_results(job_id)
            
            if retrieved_results:
                summary = retrieved_results.get("summary", {})
                datasets = retrieved_results.get("datasets", [])
                
                print(f"📊 Verification Results:")
                print(f"   Job ID: {retrieved_results.get('job_id')}")
                print(f"   Model: {summary.get('model_name')}")
                print(f"   Engine: {retrieved_results.get('engine')}")
                print(f"   Overall Accuracy: {summary.get('overall_accuracy', 0):.4f}")
                print(f"   Total Datasets: {summary.get('total_datasets', 0)}")
                print(f"   Total Examples: {summary.get('total_examples', 0)}")
                print(f"   Total Correct: {summary.get('total_correct', 0)}")
                
                for dataset in datasets:
                    print(f"   Dataset {dataset.get('dataset_name')}: {dataset.get('accuracy', 0):.4f} accuracy")
                
                # Check predictions
                predictions = await storage.get_predictions(job_id, "demo_gsm8k")
                print(f"   Predictions stored: {len(predictions)} examples")
                
                if predictions:
                    correct_count = sum(1 for p in predictions if p.get('is_correct'))
                    print(f"   Correct predictions: {correct_count}/{len(predictions)}")
            else:
                print(f"❌ Failed to retrieve saved results")
        else:
            print(f"❌ Failed to save results to ClickHouse")
        
        await storage.close()
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(process_extracted_results())