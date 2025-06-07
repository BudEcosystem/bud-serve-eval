import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import ansible_runner
import yaml

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)

# add export ANSIBLE_PYTHON_INTERPRETER=/home/ubuntu/bud-serve-eval/.venv/bin/python to sys.executable


class AnsibleOrchestrator:
    """Central job orchestrator using Ansible playbooks based on runner_type."""

    def __init__(self, playbook_dir: Optional[Path] = None):
        """Initialize the Ansible orchestrator with a playbook directory.

        Args:
            playbook_dir: Optional path to the directory containing Ansible playbooks.
                          If not provided, defaults to the repository's ansible/playbooks directory.

        Raises:
            FileNotFoundError: If the specified playbook directory does not exist.
        """
        repo_root = Path(__file__).resolve().parents[2]
        self._playbook_dir = playbook_dir or repo_root / "ansible" / "playbooks"
        if not self._playbook_dir.exists():
            raise FileNotFoundError(f"Ansible playbook directory not found: {self._playbook_dir}")

    def verify_cluster_connection(self, kubeconfig: Optional[str] = None) -> bool:
        """Verify cluster connection using an Ansible playbook via a kubeconfig in JSON form."""
        temp_id = f"verify-{uuid.uuid4().hex}"
        playbook = "verify_cluster_k8s.yml"

        files = {}
        extravars = {}

        # For Testing: Load from local yaml file if no kubeconfig provided
        if kubeconfig is None and Path("/home/ubuntu/bud-serve-eval/k3s.yaml").exists():
            # Read the local k3s.yaml file
            with open("/home/ubuntu/bud-serve-eval/k3s.yaml", "r") as f:
                kubeconfig_yaml_content = f.read()
            # Since it's already YAML, we don't need to parse/convert it
            files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml_content}
            extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
        elif kubeconfig:
            # 1) Parse the incoming JSON string into a Python dict
            kubeconfig_dict = json.loads(kubeconfig)

            # 2) Dump that dict out as YAML
            kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)

            files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml}
            extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
        else:
            # Use in-cluster config - don't pass kubeconfig_path
            extravars = {"use_in_cluster_config": True}

        try:
            self._run_ansible_playbook(playbook, temp_id, files, extravars)
            logger.info("::: EVAL Ansible ::: Ansible-based cluster verification succeeded for %s", temp_id)
            return True
        except Exception as e:
            logger.error("::: EVAL Ansible ::: Ansible-based cluster verification failed: %s", e, exc_info=True)
            return False

    def run_job(
        self,
        runner_type: str,
        uuid: str,
        kubeconfig: Optional[str],
        engine_args: Dict[str, Any],
        docker_image: str,
        namespace: str = "budeval",
        ttl_seconds: int = 600,
    ):
        """Run a job using the specified runner type.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            engine_args: Arguments to pass to the engine.
            docker_image: Docker image to use for the job.
            namespace: Kubernetes namespace to deploy the job in. Defaults to "budeval".
            ttl_seconds: Time-to-live in seconds for the job after completion. Defaults to 600.

        Raises:
            ValueError: If the specified runner_type is not supported.
        """
        playbook_map = {
            "kubernetes": "submit_job_k8s.yml",
        }
        playbook = playbook_map.get(runner_type.lower())
        if not playbook:
            raise ValueError(f"Unsupported runner_type: {runner_type}")

        job_yaml = self._render_job_yaml(uuid, docker_image, engine_args, namespace, ttl_seconds)

        files = {
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        if kubeconfig:
            # Parse and convert kubeconfig if provided
            kubeconfig_dict = json.loads(kubeconfig)
            kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        else:
            # Use in-cluster config
            extravars["use_in_cluster_config"] = True

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def run_job_with_volumes(
        self,
        runner_type: str,
        uuid: str,
        kubeconfig: Optional[str],
        engine_args: Dict[str, Any],
        docker_image: str,
        namespace: str = "budeval",
        ttl_seconds: int = 600,
        output_volume_size: str = "5Gi",
    ):
        """Run a job with persistent volumes using the specified runner type.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            engine_args: Arguments to pass to the engine.
            docker_image: Docker image to use for the job.
            namespace: Kubernetes namespace to deploy the job in. Defaults to "budeval".
            ttl_seconds: Time-to-live in seconds for the job after completion. Defaults to 600.
            output_volume_size: Size of the output persistent volume. Defaults to "5Gi".

        Raises:
            ValueError: If the specified runner_type is not supported.
        """
        playbook_map = {
            "kubernetes": "submit_job_with_volumes_k8s.yml",
        }
        playbook = playbook_map.get(runner_type.lower())
        if not playbook:
            raise ValueError(f"Unsupported runner_type: {runner_type}")

        # Generate YAML manifests for output PVC and Job (shared datasets use eval-datasets-pvc)
        pvc_output_yaml = self._render_persistent_volume_claim_yaml(
            f"{uuid}-output-pvc", f"{uuid}-output-pv", output_volume_size, namespace
        )
        job_yaml = self._render_job_with_volumes_yaml(uuid, docker_image, engine_args, namespace, ttl_seconds)

        files = {
            "pvc-output.yaml": pvc_output_yaml,
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "pvc_output_template_path": "pvc-output.yaml",
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        # For Testing: Load from local yaml file if no kubeconfig provided
        if kubeconfig is None and Path("/home/ubuntu/bud-serve-eval/k3s.yaml").exists():
            # Read the local k3s.yaml file
            with open("/home/ubuntu/bud-serve-eval/k3s.yaml", "r") as f:
                kubeconfig_yaml_content = f.read()
            # Since it's already YAML, we don't need to parse/convert it
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml_content
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        elif kubeconfig:
            # Parse and convert kubeconfig if provided
            kubeconfig_dict = json.loads(kubeconfig)
            kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        else:
            # Use in-cluster config
            extravars["use_in_cluster_config"] = True

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def cleanup_job_resources(
        self,
        uuid: str,
        kubeconfig: Optional[str],
        namespace: str = "budeval",
        eval_request_id: Optional[str] = None,
    ):
        """Clean up job resources including volumes and ConfigMaps.

        Args:
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            namespace: Kubernetes namespace. Defaults to "budeval".
            eval_request_id: Optional evaluation request ID for ConfigMap cleanup.
        """
        playbook = "cleanup_job_resources_k8s.yml"

        files = {}
        extravars = {
            "job_name": uuid,
            "namespace": namespace,
        }

        # For Testing: Load from local yaml file if no kubeconfig provided
        if kubeconfig is None and Path("/home/ubuntu/bud-serve-eval/k3s.yaml").exists():
            # Read the local k3s.yaml file
            with open("/home/ubuntu/bud-serve-eval/k3s.yaml", "r") as f:
                kubeconfig_yaml_content = f.read()
            # Since it's already YAML, we don't need to parse/convert it
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml_content
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        elif kubeconfig:
            # Parse and convert kubeconfig if provided
            kubeconfig_dict = json.loads(kubeconfig)
            kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        else:
            # Use in-cluster config
            extravars["use_in_cluster_config"] = True

        try:
            self._run_ansible_playbook(playbook, uuid, files, extravars)
            logger.info(f"Successfully cleaned up resources for job {uuid}")

            # Also cleanup ConfigMap if eval_request_id is provided
            if eval_request_id:
                try:
                    from budeval.evals.configmap_manager import ConfigMapManager

                    configmap_manager = ConfigMapManager(namespace=namespace)
                    configmap_manager.delete_opencompass_config_map(eval_request_id, kubeconfig)
                    logger.info(f"Successfully cleaned up ConfigMap for eval request {eval_request_id}")
                except Exception as configmap_e:
                    logger.warning(f"ConfigMap cleanup failed for {eval_request_id}: {configmap_e}")

        except Exception as e:
            logger.error(f"Failed to cleanup resources for job {uuid}: {e}", exc_info=True)
            raise e

    def get_job_status(
        self,
        uuid: str,
        kubeconfig: Optional[str],
        namespace: str = "budeval",
    ) -> dict:
        """Get job status.

        Args:
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            namespace: Kubernetes namespace. Defaults to "budeval".

        Returns:
            Dict containing job status information.
        """
        playbook = "get_job_status_k8s.yml"

        files = {}
        extravars = {
            "job_name": uuid,
            "namespace": namespace,
        }

        # For Testing: Load from local yaml file if no kubeconfig provided
        if kubeconfig is None and Path("/home/ubuntu/bud-serve-eval/k3s.yaml").exists():
            # Read the local k3s.yaml file
            with open("/home/ubuntu/bud-serve-eval/k3s.yaml", "r") as f:
                kubeconfig_yaml_content = f.read()
            # Since it's already YAML, we don't need to parse/convert it
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml_content
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        elif kubeconfig:
            # Parse and convert kubeconfig if provided
            kubeconfig_dict = json.loads(kubeconfig)
            kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
            files[f"{uuid}_kubeconfig.yaml"] = kubeconfig_yaml
            extravars["kubeconfig_path"] = f"{uuid}_kubeconfig.yaml"
        else:
            # Use in-cluster config
            extravars["use_in_cluster_config"] = True

        try:
            result = self._run_ansible_playbook_with_output(playbook, uuid, files, extravars)
            logger.info(f"Successfully retrieved status for job {uuid}")

            # Parse the Ansible output to extract job status
            job_status = self._parse_job_status_from_ansible_output(result, uuid)
            return job_status

        except Exception as e:
            logger.error(f"Failed to get status for job {uuid}: {e}", exc_info=True)
            return {"status": "error", "phase": "failed", "message": str(e), "active": 0, "succeeded": 0, "failed": 1}

    def _run_ansible_playbook(
        self, playbook: str, uuid: str, files: Dict[str, str], extravars: Dict[str, Any]
    ) -> None:
        playbook_path = self._playbook_dir / playbook
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        pdir = Path(tempfile.mkdtemp(prefix=f"ansible_{uuid}_"))
        logger.debug("Created private data dir: %s", pdir)

        # Write ansible.cfg to enforce interpreter and disable host key checking
        (pdir / "ansible.cfg").write_text(
            f"[defaults]\ninterpreter_python = {sys.executable}\nhost_key_checking = False\n"
        )

        # Create inventory
        (pdir / "inventory").mkdir()
        (pdir / "inventory" / "hosts").write_text(
            "[local]\nlocalhost ansible_connection=local ansible_python_interpreter=" + sys.executable + "\n"
        )

        # Write extra files at the root of private_data_dir
        for rel_path, content in files.items():
            full_path = pdir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Copy playbook into project/
        project_dir = pdir / "project"
        project_dir.mkdir()
        shutil.copy(playbook_path, project_dir / playbook)

        # Override extravars file paths to absolute paths
        if "kubeconfig_path" in extravars:
            extravars["kubeconfig_path"] = str(pdir / extravars["kubeconfig_path"])
        if "job_template_path" in extravars:
            extravars["job_template_path"] = str(pdir / extravars["job_template_path"])
        if "pv_data_template_path" in extravars:
            extravars["pv_data_template_path"] = str(pdir / extravars["pv_data_template_path"])
        if "pvc_data_template_path" in extravars:
            extravars["pvc_data_template_path"] = str(pdir / extravars["pvc_data_template_path"])
        if "pv_output_template_path" in extravars:
            extravars["pv_output_template_path"] = str(pdir / extravars["pv_output_template_path"])
        if "pvc_output_template_path" in extravars:
            extravars["pvc_output_template_path"] = str(pdir / extravars["pvc_output_template_path"])

        # Environment vars for ansible-runner
        venv_bin = os.path.dirname(sys.executable)
        current_path = os.environ.get("PATH", "")
        envvars = {
            "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "PATH": f"{venv_bin}:{current_path}",
        }

        logger.info(f"Running Ansible playbook: {playbook} with extravars: {extravars}")
        logger.info(f"Using Python interpreter: {sys.executable}")
        logger.info(f"PATH environment: {envvars['PATH']}")

        res = ansible_runner.run(
            private_data_dir=str(pdir),
            playbook=playbook,
            extravars=extravars,
            envvars=envvars,
            verbosity=2,
        )

        if res.rc != 0:
            error_msg = f"Ansible playbook failed: {playbook}, rc={res.rc}"
            if hasattr(res, "stdout") and res.stdout:
                error_msg += f", stdout: {res.stdout.read()}"
            if hasattr(res, "stderr") and res.stderr:
                error_msg += f", stderr: {res.stderr.read()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)

    def _run_ansible_playbook_with_output(
        self, playbook: str, uuid: str, files: Dict[str, str], extravars: Dict[str, Any]
    ) -> Any:
        """Run Ansible playbook and return the result object for output parsing."""
        playbook_path = self._playbook_dir / playbook
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        pdir = Path(tempfile.mkdtemp(prefix=f"ansible_{uuid}_"))
        logger.debug("Created private data dir: %s", pdir)

        # Write ansible.cfg to enforce interpreter and disable host key checking
        (pdir / "ansible.cfg").write_text(
            f"[defaults]\ninterpreter_python = {sys.executable}\nhost_key_checking = False\n"
        )

        # Create inventory
        (pdir / "inventory").mkdir()
        (pdir / "inventory" / "hosts").write_text(
            "[local]\nlocalhost ansible_connection=local ansible_python_interpreter=" + sys.executable + "\n"
        )

        # Write extra files at the root of private_data_dir
        for rel_path, content in files.items():
            full_path = pdir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Copy playbook into project/
        project_dir = pdir / "project"
        project_dir.mkdir()
        shutil.copy(playbook_path, project_dir / playbook)

        # Override extravars file paths to absolute paths
        if "kubeconfig_path" in extravars:
            extravars["kubeconfig_path"] = str(pdir / extravars["kubeconfig_path"])
        if "job_template_path" in extravars:
            extravars["job_template_path"] = str(pdir / extravars["job_template_path"])
        if "pv_data_template_path" in extravars:
            extravars["pv_data_template_path"] = str(pdir / extravars["pv_data_template_path"])
        if "pvc_data_template_path" in extravars:
            extravars["pvc_data_template_path"] = str(pdir / extravars["pvc_data_template_path"])
        if "pv_output_template_path" in extravars:
            extravars["pv_output_template_path"] = str(pdir / extravars["pv_output_template_path"])
        if "pvc_output_template_path" in extravars:
            extravars["pvc_output_template_path"] = str(pdir / extravars["pvc_output_template_path"])

        # Environment vars for ansible-runner
        venv_bin = os.path.dirname(sys.executable)
        current_path = os.environ.get("PATH", "")
        envvars = {
            "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "PATH": f"{venv_bin}:{current_path}",
        }

        logger.info(f"Running Ansible playbook: {playbook} with extravars: {extravars}")
        logger.info(f"Using Python interpreter: {sys.executable}")
        logger.info(f"PATH environment: {envvars['PATH']}")

        res = ansible_runner.run(
            private_data_dir=str(pdir),
            playbook=playbook,
            extravars=extravars,
            envvars=envvars,
            verbosity=2,
        )

        if res.rc != 0:
            error_msg = f"Ansible playbook failed: {playbook}, rc={res.rc}"
            if hasattr(res, "stdout") and res.stdout:
                error_msg += f", stdout: {res.stdout.read()}"
            if hasattr(res, "stderr") and res.stderr:
                error_msg += f", stderr: {res.stderr.read()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)
        return res

    def _parse_job_status_from_ansible_output(self, ansible_result: Any, job_name: str) -> dict:
        """Parse job status from Ansible playbook output."""
        try:
            # Default status
            status_info = {
                "status": "unknown",
                "phase": "unknown",
                "active": 0,
                "succeeded": 0,
                "failed": 0,
                "pod_count": 0,
                "data_pvc_status": "unknown",
                "output_pvc_status": "unknown",
                "message": "Status retrieved",
            }

            # Try to extract information from Ansible events
            if hasattr(ansible_result, "events"):
                for event in ansible_result.events:
                    if event.get("event") == "runner_on_ok":
                        event_data = event.get("event_data", {})
                        task_name = event_data.get("task", "")

                        # Look for the set_fact task that contains job status
                        if "Set job status facts" in task_name:
                            res = event_data.get("res", {})
                            ansible_facts = res.get("ansible_facts", {})
                            job_status = ansible_facts.get("job_status", {})

                            if job_status:
                                status_info.update(job_status)

                                # Determine overall status based on job conditions
                                # Safely convert to int, handling both string and int values
                                try:
                                    active = int(job_status.get("active", 0))
                                    succeeded = int(job_status.get("succeeded", 0))
                                    failed = int(job_status.get("failed", 0))
                                except (ValueError, TypeError):
                                    # Fallback to 0 if conversion fails
                                    active = 0
                                    succeeded = 0
                                    failed = 0

                                if succeeded > 0:
                                    status_info["status"] = "succeeded"
                                elif failed > 0:
                                    status_info["status"] = "failed"
                                elif active > 0:
                                    status_info["status"] = "running"
                                else:
                                    status_info["status"] = "pending"

                                break

            logger.debug(f"Parsed job status for {job_name}: {status_info}")
            return status_info

        except Exception as e:
            logger.error(f"Error parsing job status from Ansible output: {e}", exc_info=True)
            return {
                "status": "error",
                "phase": "unknown",
                "active": 0,
                "succeeded": 0,
                "failed": 0,
                "message": f"Error parsing status: {str(e)}",
            }

    def _render_job_yaml(self, uuid: str, docker_image: str, args: Dict[str, Any], namespace: str, ttl: int) -> str:
        safe_args = json.dumps(args)
        return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {uuid}
  namespace: {namespace}
spec:
  ttlSecondsAfterFinished: {ttl}
  template:
    spec:
      containers:
        - name: engine
          image: {docker_image}
          env:
            - name: ENGINE_ARGS
              value: '{safe_args}'
      restartPolicy: Never
  backoffLimit: 1
"""

    def _render_persistent_volume_yaml(self, name: str, size: str, volume_type: str) -> str:
        # Note: This creates a PV without hostPath
        # The actual storage backend depends on your cluster configuration
        return f"""apiVersion: v1
kind: PersistentVolume
metadata:
  name: {name}
  labels:
    type: {volume_type}
    app: budeval
spec:
  capacity:
    storage: {size}
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  # Storage provisioner will handle the actual storage backend
  # No hostPath specified
"""

    def _render_persistent_volume_claim_yaml(self, name: str, _pv_name: str, size: str, namespace: str) -> str:
        # Render a PVC using environment-aware configuration for job-specific volumes
        from budeval.commons.storage_config import StorageConfig

        job_cfg = StorageConfig.get_job_volumes_config()
        access_mode = job_cfg.get("access_mode", "ReadWriteOnce")
        storage_class = job_cfg.get("storage_class", "")

        return f"""apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    app: budeval
spec:
  accessModes:
    - {access_mode}
{f"  storageClassName: {storage_class}" if storage_class else ""}
  resources:
    requests:
      storage: {size}
"""

    def _render_job_with_volumes_yaml(
        self, uuid: str, docker_image: str, args: Dict[str, Any], namespace: str, ttl: int
    ) -> str:
        safe_args = json.dumps(args)

        # Extract eval_request_id for ConfigMap mounting
        eval_request_id = args.get("eval_request_id", uuid)
        configmap_name = f"opencompass-config-{eval_request_id.lower()}"

        # Extract datasets and append '_gen' suffix for OpenCompass
        datasets = args.get("datasets", ["mmlu"])
        datasets_with_gen = [f"{dataset}_gen" for dataset in datasets]
        datasets_arg = " ".join(datasets_with_gen)

        # Extract model configuration for CLI
        model_name = args.get("model_name", "test-model")
        api_key = args.get("api_key", "")
        base_url = args.get("base_url", "")

        # Create OpenCompass CLI arguments - use CLI mode for better compatibility  
        run_args = [
            "run.py",
            "--datasets", "mmlu_gen",
            "--hf-type", "chat", 
            "--hf-path", model_name,
            "--work-dir", "/workspace/outputs",
            "--debug"
        ]

        return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {uuid}
  namespace: {namespace}
spec:
  ttlSecondsAfterFinished: {ttl}
  template:
    spec:
      containers:
        - name: engine
          image: {docker_image}
          command: ["python"]
          args: {json.dumps(run_args)}
          env:
            - name: ENGINE_ARGS
              value: '{safe_args}'
            - name: OPENCOMPASS_CONFIG_PATH
              value: '/workspace/configs'
            - name: HF_HOME
              value: '/workspace/cache'
            - name: TRANSFORMERS_CACHE
              value: '/workspace/cache'
            - name: TORCH_HOME
              value: '/workspace/cache'
          volumeMounts:
            - name: eval-datasets
              mountPath: /workspace/data
              subPath: data
              readOnly: true
            - name: output-volume
              mountPath: /workspace/outputs
            - name: opencompass-config
              mountPath: /workspace/configs
              readOnly: true
            - name: cache-volume
              mountPath: /workspace/cache
          workingDir: /workspace
      volumes:
        - name: eval-datasets
          persistentVolumeClaim:
            claimName: eval-datasets-pvc
            # Note: This PVC must exist in the same namespace as the job
            # The eval-datasets PVC should be created in the job's namespace
        - name: output-volume
          persistentVolumeClaim:
            claimName: {uuid}-output-pvc
        - name: opencompass-config
          configMap:
            name: {configmap_name}
            items:
              - key: "bud-model.py"
                path: "bud-model.py"
              - key: "bud-datasets.py"
                path: "bud-datasets.py"
              - key: "eval_config.py"
                path: "eval_config.py"
              - key: "metadata.json"
                path: "metadata.json"
        - name: cache-volume
          emptyDir: {{}}
      restartPolicy: Never
  backoffLimit: 1
"""
