"""Kubernetes runner that launches each engine as a Kubernetes Job."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from kubernetes import client, config, watch  # pip install kubernetes
from kubernetes.client.rest import ApiException

from budeval.commons.logging import logging
from budeval.registry.engines.core import EngineMetadata

from .core import RunnerMetadata, RunnerProtocol, RunnerRegistry


logger = logging.getLogger(__name__)


@RunnerRegistry.register(
    RunnerMetadata(
        name="Kubernetes",
        version="1.0.0",
        description="Runs the engine inside a Kubernetes Job",
        author="budeval team",
        tags=["k8s", "container-orchestration"],
        capabilities=["batch", "scaling"],
        config_schema={
            "properties": {
                "namespace": {"type": "string", "default": "budeval"},
                "service_account": {"type": "string"},
                "image_pull_secrets": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "ttl_seconds_after_finish": {"type": "integer", "default": 600},
            }
        },
    )
)
class KubernetesRunner(RunnerProtocol):
    """Minimal but production-safe implementation that.

    1. Loads kube-config (in-cluster or local).
    2. Creates a *Job* object with one container running the engine's Docker image.
    3. Passes the engine arguments as a JSON string via env var ``ENGINE_ARGS``.
    4. Namespaces everything under ``budeval-<engine-name>-<timestamp>`` .
    """

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        """Initialize the Kubernetes runner with the given configuration.

        Args:
            cfg: Optional configuration dictionary for the runner.
        """
        self.cfg = cfg or {}
        try:
            # Try in-cluster first; fall back to ~/.kube/config
            config.load_incluster_config()
            logger.debug("Loaded in-cluster kube config")
        except config.config_exception.ConfigException:
            config.load_kube_config()
            logger.debug("Loaded local kube config")

        self.batch_api = client.BatchV1Api()
        self.core_api = client.CoreV1Api()
        self._namespace = self.cfg.get("namespace", "budeval")

    # ───────────────────────── RunnerProtocol ─────────────────────────

    def submit_job(
        self,
        engine_meta: EngineMetadata,
        engine_args: Dict[str, Any],
    ) -> str:
        """Submit a job to the Kubernetes cluster.

        Args:
            engine_meta: Metadata about the engine to run.
            engine_args: Arguments to pass to the engine.

        Returns:
            str: The run ID for the job.

        Raises:
            ApiException: If there is an error creating the job.
        """
        run_id = f"budeval-{engine_meta.name.lower()}-{int(time.time())}"
        container = client.V1Container(
            name="engine",
            image=engine_meta.docker_image_url,
            args=[],  # if the engine expects CLI args, build them here
            env=[
                client.V1EnvVar(name="ENGINE_ARGS", value=json.dumps(engine_args)),
            ],
            resources=client.V1ResourceRequirements(
                requests={"cpu": "1", "memory": "1Gi"},
                limits={"cpu": "2", "memory": "4Gi"},
            ),
        )

        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            service_account_name=self.cfg.get("service_account"),
            image_pull_secrets=[
                client.V1LocalObjectReference(name=s)
                for s in self.cfg.get("image_pull_secrets", [])
            ],
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"job": run_id}),
            spec=pod_spec,
        )

        job_spec = client.V1JobSpec(
            template=template,
            backoff_limit=1,
            ttl_seconds_after_finished=self.cfg.get("ttl_seconds_after_finish", 600),
        )

        job = client.V1Job(
            metadata=client.V1ObjectMeta(name=run_id, namespace=self._namespace),
            spec=job_spec,
        )

        try:
            self.batch_api.create_namespaced_job(namespace=self._namespace, body=job)
            logger.info("Submitted Job %s in ns=%s", run_id, self._namespace)
            return run_id
        except ApiException as e:
            logger.error("Failed to create Job: %s", e)
            raise

    def get_job_status(self, run_id: str) -> str:
        """Get the status of a job in the Kubernetes cluster.

        Args:
            run_id: The ID of the job to check.

        Returns:
            str: The status of the job (SUCCEEDED, FAILED, RUNNING, or PENDING).
        """
        job = self.batch_api.read_namespaced_job_status(run_id, self._namespace)
        if job and job.status:
            if job.status.succeeded:
                return "SUCCEEDED"
            if job.status.failed:
                return "FAILED"
            if job.status.active:
                return "RUNNING"
        return "PENDING"

    def stop_job(self, run_id: str) -> None:
        """Stop a running job in the Kubernetes cluster.

        Args:
            run_id: The ID of the job to stop.
        """
        propagation = client.V1DeleteOptions(propagation_policy="Foreground")
        self.batch_api.delete_namespaced_job(
            name=run_id,
            namespace=self._namespace,
            body=propagation,
        )
        logger.info("Deleted Job %s", run_id)

    def get_job_logs(self, run_id: str, follow: bool = False) -> str:
        """Get logs from a job in the Kubernetes cluster.

        Args:
            run_id: The ID of the job to get logs from.
            follow: Whether to follow the logs in real-time.

        Returns:
            str: The logs from the job.
        """
        # Look up the single pod belonging to the job
        pods = self.core_api.list_namespaced_pod(
            namespace=self._namespace,
            label_selector=f"job={run_id}",
        )
        if not pods.items:
            return ""
        pod_name = pods.items[0].metadata.name
        if follow:
            w = watch.Watch()
            out = []
            for e in w.stream(
                self.core_api.read_namespaced_pod_log,
                name=pod_name,
                namespace=self._namespace,
                follow=True,
            ):
                print(e, end="")
                out.append(e)
            return "".join(out)
        else:
            return self.core_api.read_namespaced_pod_log(
                name=pod_name, namespace=self._namespace
            )
