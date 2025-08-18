#!/usr/bin/env python3
"""
Check data in ClickHouse tables.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def check_clickhouse_data():
    """Check what data exists in ClickHouse."""
    print("🔍 Checking ClickHouse data...")
    
    try:
        # Get ClickHouse storage
        ch_storage = get_storage_adapter("clickhouse")
        await initialize_storage(ch_storage)
        
        # Check connectivity
        if not await ch_storage.health_check():
            print("❌ ClickHouse connection failed")
            return
        
        print("✅ Connected to ClickHouse")
        
        # Check table counts
        async with ch_storage.get_connection() as conn:
            async with conn.cursor() as cursor:
                # Check each table
                tables = ['budeval.evaluation_jobs', 'budeval.dataset_results', 'budeval.predictions']
                
                for table in tables:
                    await cursor.execute(f"SELECT count() FROM {table}")
                    count = await cursor.fetchone()
                    print(f"📊 {table}: {count[0]} records")
                
                # List all job IDs
                await cursor.execute("SELECT job_id, model_name, overall_accuracy, created_at FROM budeval.evaluation_jobs ORDER BY created_at DESC")
                jobs = await cursor.fetchall()
                
                if jobs:
                    print(f"\n📋 Jobs in ClickHouse:")
                    for job in jobs:
                        print(f"   - {job[0]} | {job[1]} | {job[2]:.4f} accuracy | {job[3]}")
                else:
                    print(f"\n📋 No jobs found in ClickHouse")
        
        await ch_storage.close()
        
    except Exception as e:
        print(f"❌ Failed to check ClickHouse data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_clickhouse_data())