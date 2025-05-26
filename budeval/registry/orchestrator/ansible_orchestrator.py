import sys
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import ansible_runner
import yaml

from budeval.commons.logging import logging

logger = logging.getLogger(__name__)


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

    def verify_cluster_connection(self, kubeconfig: str) -> bool:
        """Verify cluster connection using an Ansible playbook via a kubeconfig in JSON form."""
        temp_id = f"verify-{uuid.uuid4().hex}"
        playbook = "verify_cluster_k8s.yml"

        # 1) Parse the incoming JSON string into a Python dict
        kubeconfig_dict = json.loads(kubeconfig)

        # 2) Dump that dict out as YAML
        kubeconfig_yaml = yaml.safe_dump(
            kubeconfig_dict,
            sort_keys=False,
            default_flow_style=False
        )

        files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml}
        extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}

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
        kubeconfig: str,
        engine_args: Dict[str, Any],
        docker_image: str,
        namespace: str = "budeval",
        ttl_seconds: int = 600,
    ):
        """Run a job using the specified runner type.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a string.
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
            f"{uuid}_kubeconfig.yaml": kubeconfig,
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "kubeconfig_path": f"{uuid}_kubeconfig.yaml",
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def _run_ansible_playbook(self, playbook: str, uuid: str, files: Dict[str, str], extravars: Dict[str, Any]) -> None:
        playbook_path = self._playbook_dir / playbook
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        pdir = Path(tempfile.mkdtemp(prefix=f"ansible_{uuid}_"))
        logger.debug("Created private data dir: %s", pdir)

        # Write ansible.cfg to enforce interpreter and disable host key checking
        (pdir / "ansible.cfg").write_text(
            "[defaults]\n"
            f"interpreter_python = {sys.executable}\n"
            "host_key_checking = False\n"
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

        # Environment vars for ansible-runner
        envvars = {
            "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
            "ANSIBLE_HOST_KEY_CHECKING": "False",
        }

        res = ansible_runner.run(
            private_data_dir=str(pdir),
            playbook=playbook,
            extravars=extravars,
            envvars=envvars,
            verbosity=2,
        )

        if res.rc != 0:
            raise RuntimeError(f"Ansible playbook failed: {playbook}, rc={res.rc}")
        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)

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
