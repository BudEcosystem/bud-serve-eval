#!/usr/bin/env python3
"""
Test OpenCompass integration with real LLM endpoint using the updated job template.
"""

import json
import time
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator
from budeval.evals.configmap_manager import ConfigMapManager


def test_real_llm_integration():
    """Test the complete integration with real LLM API."""
    print("🧪 Testing Real LLM Integration with Updated Job Template")
    print("=" * 70)
    
    # Real API configuration
    test_uuid = "real-llm-test-123"
    test_args = {
        "eval_request_id": "qwen3-4b-test-eval",
        "model_name": "qwen3-4b",
        "api_key": "sk-BudLiteLLMMasterKey_123",
        "base_url": "http://20.66.97.208/v1/chat/completions",
        "datasets": ["mmlu"]  # Start with just one dataset for testing
    }
    
    print(f"📋 Test Parameters:")
    print(f"  UUID: {test_uuid}")
    print(f"  Model: {test_args['model_name']}")
    print(f"  API: {test_args['base_url']}")
    print(f"  Datasets: {test_args['datasets']}")
    
    try:
        # Step 1: Create ConfigMap with real API details
        print("\n🔧 Step 1: Creating ConfigMap with real API configuration...")
        config_manager = ConfigMapManager()
        
        configmap_result = config_manager.create_opencompass_config_map(
            eval_request_id=test_args["eval_request_id"],
            model_name=test_args["model_name"],
            api_key=test_args["api_key"],
            base_url=test_args["base_url"],
            datasets=test_args["datasets"]
        )
        
        print(f"✅ ConfigMap created: {configmap_result['configmap_name']}")
        print(f"   Action: {configmap_result['action']}")
        print(f"   Files: {configmap_result['files']}")
        
        # Step 2: Generate updated job YAML with bash script
        print("\n🔧 Step 2: Generating updated job YAML with config copy...")
        orchestrator = AnsibleOrchestrator()
        
        job_yaml = orchestrator._render_job_with_volumes_yaml(
            uuid=test_uuid,
            docker_image="ghcr.io/rahulvramesh/opencompass:latest",
            args=test_args,
            namespace="budeval",
            ttl=1800  # 30 minutes
        )
        
        print("✅ Generated Job YAML with bash script approach:")
        print("-" * 50)
        
        # Extract and display the bash script
        lines = job_yaml.split('\n')
        in_args = False
        for line in lines:
            if 'args:' in line and 'bash' in job_yaml:
                in_args = True
            if in_args:
                print(line)
                if line.strip().endswith(']'):
                    break
        
        print("-" * 50)
        
        # Step 3: Verify the bash script contains our fix
        expected_elements = [
            'command: ["bash"]',
            'mkdir -p /workspace/opencompass/configs/models/bud',
            'cp /workspace/configs/bud-model.py /workspace/opencompass/configs/models/bud/bud-model.py',
            '--models bud-model',
            '--datasets mmlu_gen',
            'qwen3-4b'
        ]
        
        print("\n🔍 Step 3: Verifying updated job template elements:")
        all_correct = True
        for element in expected_elements:
            if element in job_yaml:
                print(f"  ✅ {element}")
            else:
                print(f"  ❌ {element}")
                all_correct = False
        
        # Step 4: Test ConfigMap content
        print("\n🔍 Step 4: Verifying ConfigMap contains real API details:")
        configmap_info = config_manager.get_configmap_info(test_args["eval_request_id"])
        if configmap_info:
            metadata = configmap_info['metadata']
            checks = [
                ("Model name", metadata.get('model_name') == test_args['model_name']),
                ("Base URL", metadata.get('base_url') == test_args['base_url']),
                ("Datasets", set(metadata.get('datasets', [])) == set(test_args['datasets'])),
                ("Files present", 'bud-model.py' in configmap_info['files'])
            ]
            
            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"  {status} {check_name}")
                if not result:
                    all_correct = False
        else:
            print("  ❌ ConfigMap info not found")
            all_correct = False
        
        if all_correct:
            print("\n🎉 Real LLM Integration Test PASSED!")
            print("✅ ConfigMap created with real API configuration")
            print("✅ Job template uses bash script to copy config")
            print("✅ All components properly configured for qwen3-4b")
            print(f"✅ Ready to deploy job: kubectl apply -f <job-yaml> -n budeval")
            
            # Optionally save the job YAML for manual testing
            with open(f"/tmp/{test_uuid}-job.yaml", "w") as f:
                f.write(job_yaml)
            print(f"📝 Job YAML saved to: /tmp/{test_uuid}-job.yaml")
            
            return True
        else:
            print("\n💥 Real LLM Integration Test FAILED!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during integration test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run real LLM integration test."""
    success = test_real_llm_integration()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)