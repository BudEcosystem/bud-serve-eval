#!/usr/bin/env python3
"""
Quick verification of ClickHouse data.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def verify_clickhouse_data():
    """Quick verification of ClickHouse data."""
    print("🔍 Verifying ClickHouse data...")
    
    try:
        storage = get_storage_adapter("clickhouse")
        await initialize_storage(storage)
        
        async with storage.get_connection() as conn:
            async with conn.cursor() as cursor:
                # Get latest job
                await cursor.execute("""
                    SELECT 
                        job_id, 
                        model_name, 
                        overall_accuracy, 
                        total_examples, 
                        total_correct,
                        extracted_at
                    FROM budeval.evaluation_jobs 
                    ORDER BY extracted_at DESC 
                    LIMIT 1
                """)
                job = await cursor.fetchone()
                
                if job:
                    print(f"📈 Latest Job: {job[0]}")
                    print(f"🤖 Model: {job[1]}")
                    print(f"🎯 Accuracy: {job[2]:.2%}")
                    print(f"📊 Examples: {job[4]}/{job[3]} correct")
                    print(f"📅 Extracted: {job[5]}")
                    
                    # Count predictions
                    await cursor.execute("SELECT COUNT(*) FROM budeval.predictions WHERE job_id = %(job_id)s", {"job_id": job[0]})
                    pred_count = await cursor.fetchone()
                    print(f"💭 Predictions: {pred_count[0]}")
                    
                    # Check schema first
                    await cursor.execute("DESCRIBE TABLE budeval.predictions")
                    schema = await cursor.fetchall()
                    print(f"📋 Predictions table columns: {[col[0] for col in schema]}")
                    
                    # Sample prediction with correct column names
                    await cursor.execute("""
                        SELECT example_id, model_answer, is_correct 
                        FROM budeval.predictions 
                        WHERE job_id = %(job_id)s 
                        LIMIT 3
                    """, {"job_id": job[0]})
                    samples = await cursor.fetchall()
                    
                    print("📝 Sample Predictions:")
                    for sample in samples:
                        status = "✅" if sample[2] else "❌"
                        print(f"   {status} {sample[0]}: {sample[1]}")
                    
                    print("🎉 ClickHouse integration verified successfully!")
                else:
                    print("❌ No jobs found in ClickHouse")
        
        await storage.close()
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_clickhouse_data())