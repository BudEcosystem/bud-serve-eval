#!/usr/bin/env python3
"""Test the volume initialization functionality."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from budeval.evals.volume_init import VolumeInitializer


async def test_volume_init():
    """Test volume initialization."""
    print("Testing volume initialization...")
    
    volume_init = VolumeInitializer()
    
    # Test with no kubeconfig (will use local k3s.yaml if exists)
    await volume_init.ensure_eval_datasets_volume()
    
    print("Volume initialization test completed!")


if __name__ == "__main__":
    asyncio.run(test_volume_init())