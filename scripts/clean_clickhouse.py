#!/usr/bin/env python3
"""
Clean ClickHouse database tables for fresh testing.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import get_storage_adapter, initialize_storage


async def clean_clickhouse():
    """Clean all data from ClickHouse tables."""
    print("🧹 Cleaning ClickHouse database...")
    
    try:
        # Get ClickHouse storage
        ch_storage = get_storage_adapter("clickhouse")
        await initialize_storage(ch_storage)
        
        # Check connectivity
        if not await ch_storage.health_check():
            print("❌ ClickHouse connection failed")
            return
        
        print("✅ Connected to ClickHouse")
        
        # Clean tables in reverse dependency order
        tables_to_clean = [
            'budeval.predictions',
            'budeval.dataset_results', 
            'budeval.evaluation_jobs'
        ]
        
        async with ch_storage.get_connection() as conn:
            for table in tables_to_clean:
                try:
                    query = f"TRUNCATE TABLE {table}"
                    async with conn.cursor() as cursor:
                        await cursor.execute(query)
                    print(f"🗑️  Cleaned table: {table}")
                except Exception as e:
                    print(f"⚠️  Failed to clean {table}: {e}")
        
        print("✅ ClickHouse database cleaned successfully")
        
        # Verify tables are empty
        async with ch_storage.get_connection() as conn:
            async with conn.cursor() as cursor:
                for table in tables_to_clean:
                    await cursor.execute(f"SELECT count() FROM {table}")
                    count = await cursor.fetchone()
                    print(f"📊 {table}: {count[0]} records")
        
        await ch_storage.close()
        
    except Exception as e:
        print(f"❌ Failed to clean ClickHouse: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(clean_clickhouse())