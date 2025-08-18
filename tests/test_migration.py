#!/usr/bin/env python3
"""
Test script for data migration between storage backends.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from budeval.evals.storage.factory import migrate_data, get_storage_adapter, initialize_storage


async def test_migration():
    """Test migration from filesystem to ClickHouse."""
    print("🚀 Starting migration test...")
    
    try:
        # First, let's check what data we have in filesystem storage
        fs_storage = get_storage_adapter("filesystem")
        await initialize_storage(fs_storage)
        
        job_ids = await fs_storage.list_results()
        print(f"📁 Found {len(job_ids)} jobs in filesystem storage")
        
        if not job_ids:
            print("⚠️  No data to migrate from filesystem storage")
            return
        
        # Show sample job
        if job_ids:
            sample_job_id = job_ids[0]
            sample_results = await fs_storage.get_results(sample_job_id)
            print(f"📋 Sample job {sample_job_id}:")
            if sample_results:
                summary = sample_results.get("summary", {})
                print(f"   Model: {summary.get('model_name', 'Unknown')}")
                print(f"   Accuracy: {summary.get('overall_accuracy', 0):.4f}")
                print(f"   Datasets: {summary.get('total_datasets', 0)}")
                print(f"   Examples: {summary.get('total_examples', 0)}")
        
        # Test ClickHouse connectivity first
        print("\n🔗 Testing ClickHouse connectivity...")
        ch_storage = get_storage_adapter("clickhouse")
        await initialize_storage(ch_storage)
        
        if await ch_storage.health_check():
            print("✅ ClickHouse connection successful")
        else:
            print("❌ ClickHouse connection failed")
            return
        
        # Run migration
        print(f"\n📦 Migrating {len(job_ids)} jobs from filesystem to ClickHouse...")
        stats = await migrate_data(
            source_backend="filesystem",
            target_backend="clickhouse", 
            job_ids=job_ids[:3],  # Migrate first 3 jobs as test
            verify=True,
            cleanup_source=False  # Don't cleanup for safety
        )
        
        # Display results
        print(f"\n📊 Migration Results:")
        print(f"   Total jobs: {stats['total_jobs']}")
        print(f"   Migrated: {stats['migrated_jobs']}")
        print(f"   Failed: {stats['failed_jobs']}")
        print(f"   Verified: {stats['verified_jobs']}")
        print(f"   Errors: {len(stats['errors'])}")
        
        if stats['errors']:
            print("\n❌ Errors encountered:")
            for error in stats['errors']:
                print(f"   - {error}")
        
        # Test retrieval from ClickHouse
        if stats['migrated_jobs'] > 0:
            print(f"\n🔍 Testing retrieval from ClickHouse...")
            test_job_id = job_ids[0]
            ch_results = await ch_storage.get_results(test_job_id)
            
            if ch_results:
                summary = ch_results.get("summary", {})
                print(f"✅ Successfully retrieved job {test_job_id} from ClickHouse:")
                print(f"   Model: {summary.get('model_name', 'Unknown')}")
                print(f"   Accuracy: {summary.get('overall_accuracy', 0):.4f}")
                print(f"   Datasets: {len(ch_results.get('datasets', []))}")
            else:
                print(f"❌ Failed to retrieve job {test_job_id} from ClickHouse")
        
        print("\n✅ Migration test completed!")
        
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_migration())