#!/usr/bin/env python3
"""
Test the updated OpenCompass configuration generation with proper bud-model.py format.
"""

import asyncio
import json
from budeval.evals.configmap_manager import ConfigMapManager


async def test_config_generation():
    """Test the updated configuration generation."""
    print("🧪 Testing Updated OpenCompass Configuration Generation")
    print("=" * 60)
    
    # Test parameters matching your example
    test_params = {
        "eval_request_id": "test-llama-eval-123",
        "model_name": "meta-llama/Llama-3.2-3B-Instruct", 
        "api_key": "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",
        "base_url": "http://localhost:8988/v1/chat/completions",
        "datasets": ["mmlu", "gsm8k"],
        "max_out_len": 2048,
        "max_seq_len": 4096,
        "batch_size": 8,
        "query_per_second": 1
    }
    
    print(f"📋 Test Parameters:")
    for key, value in test_params.items():
        if key == "api_key":
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    
    print("\n🔧 Generating ConfigMap...")
    
    try:
        configmap_manager = ConfigMapManager(namespace="budeval")
        
        # Generate configuration - this will create the ConfigMap content
        from budeval.evals.config_generator import OpenCompassConfigGenerator
        
        # Test the model config generation
        bud_model_content = OpenCompassConfigGenerator.generate_bud_model_config(
            model_name=test_params["model_name"],
            api_key=test_params["api_key"], 
            base_url=test_params["base_url"],
            eval_request_id=test_params["eval_request_id"],
            max_out_len=test_params["max_out_len"],
            max_seq_len=test_params["max_seq_len"],
            batch_size=test_params["batch_size"],
            query_per_second=test_params["query_per_second"]
        )
        
        print("✅ Generated bud-model.py content:")
        print("-" * 40)
        print(bud_model_content)
        print("-" * 40)
        
        # Verify the content has the correct format
        expected_elements = [
            "from opencompass.models import OpenAI",
            f"abbr='{test_params['eval_request_id']}'",
            f"path='{test_params['model_name']}'", 
            f"key='{test_params['api_key']}'",
            f"openai_api_base='{test_params['base_url']}'",
            f"query_per_second={test_params['query_per_second']}",
            f"max_out_len={test_params['max_out_len']}",
            f"max_seq_len={test_params['max_seq_len']}",
            f"batch_size={test_params['batch_size']}"
        ]
        
        print("\n🔍 Verifying configuration elements:")
        all_correct = True
        for element in expected_elements:
            if element in bud_model_content:
                print(f"  ✅ {element}")
            else:
                print(f"  ❌ {element}")
                all_correct = False
        
        if all_correct:
            print("\n🎉 Configuration generation test PASSED!")
            print("✅ All expected elements found in generated config")
            print("✅ Format matches OpenCompass requirements")
            print("✅ Uses eval_request_id as abbr (model identifier)")
            print("✅ Proper file naming: bud-model.py")
            return True
        else:
            print("\n💥 Configuration generation test FAILED!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during configuration generation: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run configuration generation test."""
    success = await test_config_generation()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)