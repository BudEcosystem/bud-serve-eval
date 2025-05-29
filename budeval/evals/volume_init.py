"""Volume initialization module for ensuring required persistent volumes exist."""

import uuid
from typing import Optional

from budeval.commons.logging import logging
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

logger = logging.getLogger(__name__)


class VolumeInitializer:
    """Handles initialization of required persistent volumes."""
    
    _initialized = False
    
    def __init__(self):
        self.orchestrator = AnsibleOrchestrator()
        
    async def ensure_eval_datasets_volume(self, kubeconfig: Optional[str] = None):
        """Ensure the eval-datasets volume exists in the budeval namespace.
        
        Args:
            kubeconfig: Optional kubernetes config. If not provided, uses in-cluster config.
        """
        # Skip if already initialized
        if VolumeInitializer._initialized:
            logger.debug("Volume initialization already completed, skipping")
            return
            
        logger.info("Ensuring eval-datasets volume exists in budeval namespace")
        logger.info(f"Kubeconfig provided: {kubeconfig is not None}")
        
        try:
            # Generate a unique ID for this operation
            operation_id = f"volume-init-{uuid.uuid4().hex[:8]}"
            logger.info(f"Volume init operation ID: {operation_id}")
            
            # Use the ensure_eval_datasets_volume playbook
            playbook = "ensure_eval_datasets_volume.yml"
            logger.info(f"Using playbook: {playbook}")
            
            # Prepare files and extravars
            files = {}
            extravars = {}
            
            # Get storage configuration based on environment
            from budeval.commons.storage_config import StorageConfig
            
            storage_config = StorageConfig.get_eval_datasets_config()
            environment = StorageConfig.get_environment()
            
            logger.info(f"Detected environment: {environment}")
            logger.info(f"Storage configuration: {storage_config}")
            
            # Set storage parameters from config
            extravars["access_mode"] = storage_config["access_mode"]
            extravars["volume_size"] = storage_config["size"]
            extravars["storage_class"] = storage_config.get("storage_class", "")
            
            # Handle kubeconfig same as other methods
            if kubeconfig:
                import json
                import yaml
                logger.info("Using provided kubeconfig")
                kubeconfig_dict = json.loads(kubeconfig)
                kubeconfig_yaml = yaml.safe_dump(
                    kubeconfig_dict,
                    sort_keys=False,
                    default_flow_style=False
                )
                files[f"{operation_id}_kubeconfig.yaml"] = kubeconfig_yaml
                extravars["kubeconfig_path"] = f"{operation_id}_kubeconfig.yaml"
            else:
                logger.info("No kubeconfig provided, will use in-cluster config or local k3s.yaml")
            
            # Run the playbook
            logger.info(f"Running ansible playbook with access_mode={extravars.get('access_mode', 'default')}")
            self.orchestrator._run_ansible_playbook(playbook, operation_id, files, extravars)
            logger.info("Successfully ensured eval-datasets volume exists")
            
            # Mark as initialized
            VolumeInitializer._initialized = True
                
        except Exception as e:
            logger.error(f"Failed to ensure eval-datasets volume: {e}", exc_info=True)
            # Don't fail the startup, just log the error