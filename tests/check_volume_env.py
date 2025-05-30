#!/usr/bin/env python3
"""Check volume configuration based on environment."""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from budeval.commons.storage_config import StorageConfig


def main():
    print("=" * 60)
    print("Storage Configuration Check")
    print("=" * 60)
    
    # Get environment
    env = StorageConfig.get_environment()
    print(f"Detected Environment: {env}")
    
    # Get full config
    config = StorageConfig.get_storage_config()
    print(f"\nFull Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # Get eval datasets config
    eval_config = StorageConfig.get_eval_datasets_config()
    print(f"\nEval Datasets Volume Configuration:")
    print(f"  Access Mode: {eval_config['access_mode']}")
    print(f"  Size: {eval_config['size']}")
    print(f"  Storage Class: {eval_config.get('storage_class', 'default')}")
    
    # Get job volumes config
    job_config = StorageConfig.get_job_volumes_config()
    print(f"\nJob Volumes Configuration:")
    print(f"  Access Mode: {job_config['access_mode']}")
    print(f"  Data Size: {job_config['data_size']}")
    print(f"  Output Size: {job_config['output_size']}")
    print(f"  Storage Class: {job_config.get('storage_class', 'default')}")
    
    print("\nNotes:")
    if env == "local":
        print("- Local environment detected (k3s.yaml found)")
        print("- Using ReadWriteOnce for compatibility with local-path provisioner")
        print("- Smaller volume sizes for development")
    else:
        print("- Production/Cloud environment detected")
        print("- Using ReadWriteMany for shared dataset access")
        print("- Larger volume sizes for production workloads")
    
    print("=" * 60)


if __name__ == "__main__":
    main()