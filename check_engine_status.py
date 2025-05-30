#!/usr/bin/env python3
"""Check evaluation engine preloading status."""

import subprocess
import json
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from budeval.registry.engines.core import EngineRegistry
    from budeval.evals.engine_preloader import EnginePreloader
except ImportError as e:
    print(f"Failed to import modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def check_kubernetes_engines():
    """Check engine preloading status in Kubernetes."""
    print("=" * 60)
    print("Kubernetes Engine Preloading Status")
    print("=" * 60)
    
    try:
        # Check if preloaded-engines ConfigMap exists
        result = subprocess.run([
            "kubectl", "get", "configmap", "preloaded-engines", 
            "-n", "budeval", "-o", "json"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            config_map = json.loads(result.stdout)
            engines_data = json.loads(config_map['data']['engines'])
            last_updated = config_map['data']['last_updated']
            preload_method = config_map['data'].get('preload_method', 'unknown')
            
            print(f"✅ Engine preloading ConfigMap found")
            print(f"📅 Last updated: {last_updated}")
            print(f"🔧 Preloaded engines: {len(engines_data)}")
            print(f"⚙️ Preload method: {preload_method}")
            print()
            
            for engine_name, engine_info in engines_data.items():
                print(f"  • {engine_name}")
                print(f"    Image: {engine_info['image']}")
                print(f"    Version: {engine_info['version']}")
                print(f"    Preloaded at: {engine_info['preloaded_at']}")
                print(f"    Method: {engine_info.get('method', 'legacy')}")
                print()
        else:
            print("❌ No preloaded-engines ConfigMap found")
            print("   Engines have not been preloaded yet")
            
    except Exception as e:
        print(f"❌ Failed to check Kubernetes engine status: {e}")


def check_local_engine_registry():
    """Check the local engine registry."""
    print("=" * 60)
    print("Local Engine Registry Status")
    print("=" * 60)
    
    try:
        # Get all registered engines
        registered_engines = EngineRegistry.list_engines()
        
        print(f"📋 Total registered engines: {len(registered_engines)}")
        print(f"🔄 Engine preloader initialized: {EnginePreloader.is_initialized()}")
        print(f"✅ Preloaded engines count: {len(EnginePreloader.get_preloaded_engines())}")
        print()
        
        if registered_engines:
            print("Registered engines:")
            for engine_name, metadata in registered_engines.items():
                preloaded = EnginePreloader.is_engine_preloaded(engine_name)
                status = "✅ Preloaded" if preloaded else "⏳ Not preloaded"
                print(f"  • {engine_name} ({metadata.version}) - {status}")
                print(f"    Image: {metadata.docker_image_url}")
                print(f"    Description: {metadata.description}")
                print()
        else:
            print("❌ No engines registered")
            
    except Exception as e:
        print(f"❌ Failed to check local engine registry: {e}")


def check_running_jobs():
    """Check if there are any engine preloading jobs running."""
    print("=" * 60)
    print("Engine Preloading Jobs Status")
    print("=" * 60)
    
    try:
        # Check for running engine preloader jobs
        result = subprocess.run([
            "kubectl", "get", "jobs", "-n", "budeval", 
            "-l", "purpose=image-preloader", "--no-headers"
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            jobs = result.stdout.strip().split('\n')
            print(f"🔄 Found {len(jobs)} engine preloading jobs:")
            for job in jobs:
                print(f"  • {job}")
                
                # Get logs for the job pods
                job_name = job.split()[0]
                logs_result = subprocess.run([
                    "kubectl", "logs", "-n", "budeval", f"job/{job_name}", "--tail=3"
                ], capture_output=True, text=True)
                
                if logs_result.returncode == 0:
                    print(f"    Recent logs:")
                    for line in logs_result.stdout.strip().split('\n')[-3:]:
                        if line.strip():
                            print(f"      {line}")
                print()
        else:
            print("✅ No engine preloading jobs currently running")
            
        # Also check for completed jobs
        completed_result = subprocess.run([
            "kubectl", "get", "jobs", "-n", "budeval", 
            "-l", "purpose=image-preloader", "--field-selector=status.successful>0", "--no-headers"
        ], capture_output=True, text=True)
        
        if completed_result.returncode == 0 and completed_result.stdout.strip():
            completed_jobs = completed_result.stdout.strip().split('\n')
            print(f"✅ Found {len(completed_jobs)} completed preloading jobs:")
            for job in completed_jobs:
                print(f"  • {job}")
            print()
            
    except Exception as e:
        print(f"❌ Failed to check running jobs: {e}")


def check_container_runtime():
    """Check the container runtime being used."""
    print("=" * 60)
    print("Container Runtime Detection")
    print("=" * 60)
    
    try:
        # Check if this is K3s
        k3s_result = subprocess.run([
            "kubectl", "get", "nodes", "-o", "jsonpath={.items[0].status.nodeInfo.containerRuntimeVersion}"
        ], capture_output=True, text=True)
        
        if k3s_result.returncode == 0:
            runtime_version = k3s_result.stdout.strip()
            print(f"🔧 Container runtime: {runtime_version}")
            
            if "containerd" in runtime_version.lower():
                print("📦 Runtime type: containerd (K3s compatible)")
                print("✅ Kubernetes-native preloading fully supported")
            elif "docker" in runtime_version.lower():
                print("🐳 Runtime type: Docker")
                print("✅ Kubernetes-native preloading fully supported")
            else:
                print(f"🔍 Runtime type: {runtime_version}")
                print("✅ Should be compatible with Kubernetes-native preloading")
        else:
            print("❌ Could not detect container runtime")
            
    except Exception as e:
        print(f"❌ Failed to check container runtime: {e}")


def check_docker_images():
    """Check if engine Docker images are available on cluster nodes."""
    print("=" * 60)
    print("Container Image Availability")
    print("=" * 60)
    
    try:
        # Get registered engines to check their images
        registered_engines = EngineRegistry.list_engines()
        
        if not registered_engines:
            print("❌ No engines registered to check")
            return
            
        for engine_name, metadata in registered_engines.items():
            image = metadata.docker_image_url
            print(f"Checking {engine_name}: {image}")
            
            # Create a temporary pod to check if image is available
            result = subprocess.run([
                "kubectl", "run", f"check-{engine_name.lower()}", 
                "-n", "budeval", "--rm", "-i", "--restart=Never",
                f"--image={image}", "--", "echo", "Image available"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"  ✅ Image available and cached")
            else:
                print(f"  ❌ Image not available or failed to pull")
                if "ErrImagePull" in result.stderr:
                    print(f"    Error: Image pull failed")
                elif "ImagePullBackOff" in result.stderr:
                    print(f"    Error: Image pull backoff")
                
    except Exception as e:
        print(f"❌ Failed to check container images: {e}")


def main():
    """Main function to check all engine preloading status."""
    print("🔍 Evaluation Engine Preloading Status Check")
    print()
    
    # Check local registry first
    check_local_engine_registry()
    print()
    
    # Check container runtime
    check_container_runtime()
    print()
    
    # Check Kubernetes status
    check_kubernetes_engines()
    print()
    
    # Check running jobs
    check_running_jobs()
    print()
    
    # Check Docker images (optional, can be slow)
    if len(sys.argv) > 1 and sys.argv[1] == "--check-images":
        check_docker_images()
        print()
    
    print("💡 Tips:")
    print("  • Use --check-images flag to verify container image availability")
    print("  • Check application logs for engine preloading progress")
    print("  • Use 'kubectl get configmap preloaded-engines -n budeval -o yaml' for detailed info")
    print("  • Use 'kubectl get jobs -n budeval -l purpose=image-preloader' to see preload jobs")
    print("  • API endpoint: GET /evals/engine-status for programmatic access")


if __name__ == "__main__":
    main() 