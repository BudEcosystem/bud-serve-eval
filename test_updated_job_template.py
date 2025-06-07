#!/usr/bin/env python3
"""
Test the updated job template with --models bud-model command.
"""

import json
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator


def test_job_template_generation():
    """Test the updated job template generation."""
    print("🧪 Testing Updated Job Template Generation")
    print("=" * 60)
    
    orchestrator = AnsibleOrchestrator()
    
    # Test parameters
    test_uuid = "test-job-123"
    test_args = {
        "eval_request_id": "test-llama-eval-123",
        "model_name": "meta-llama/Llama-3.2-3B-Instruct",
        "api_key": "test-key",
        "base_url": "http://localhost:8988/v1/chat/completions",
        "datasets": ["mmlu", "gsm8k"]
    }
    
    print(f"📋 Test Parameters:")
    print(f"  UUID: {test_uuid}")
    print(f"  Datasets: {test_args['datasets']}")
    print(f"  Model: {test_args['model_name']}")
    
    print("\n🔧 Generating Job YAML...")
    
    try:
        job_yaml = orchestrator._render_job_with_volumes_yaml(
            uuid=test_uuid,
            docker_image="ghcr.io/rahulvramesh/opencompass:latest",
            args=test_args,
            namespace="budeval",
            ttl=600
        )
        
        print("✅ Generated Job YAML:")
        print("-" * 40)
        print(job_yaml)
        print("-" * 40)
        
        # Verify the command structure
        expected_elements = [
            'command: ["python"]',
            '"run.py"',
            '"--models"',
            '"bud-model"',
            '"--datasets"',
            '"mmlu_gen gsm8k_gen"',
            '"--work-dir"',
            '"/workspace/outputs"',
            '"--debug"'
        ]
        
        print("\n🔍 Verifying command elements:")
        all_correct = True
        for element in expected_elements:
            if element in job_yaml:
                print(f"  ✅ {element}")
            else:
                print(f"  ❌ {element}")
                all_correct = False
        
        # Verify volume mounts
        volume_checks = [
            "/workspace/data",
            "/workspace/outputs", 
            "/workspace/configs",
            "/workspace/cache",
            "subPath: data",
            "bud-model.py"
        ]
        
        print("\n🔍 Verifying volume mounts:")
        for check in volume_checks:
            if check in job_yaml:
                print(f"  ✅ {check}")
            else:
                print(f"  ❌ {check}")
                all_correct = False
        
        if all_correct:
            print("\n🎉 Job template generation test PASSED!")
            print("✅ Uses --models bud-model (config file approach)")
            print("✅ Datasets properly formatted with _gen suffix")
            print("✅ Debug mode enabled")
            print("✅ All volume mounts configured correctly")
            return True
        else:
            print("\n💥 Job template generation test FAILED!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during job template generation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run job template generation test."""
    success = test_job_template_generation()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)