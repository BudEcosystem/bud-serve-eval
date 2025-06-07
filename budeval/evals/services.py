from typing import Optional, Union

from budmicroframe.commons.schemas import ErrorResponse, WorkflowMetadataResponse

from budeval.commons.logging import logging
from budeval.evals.kubernetes import KubernetesClusterHandler
from budeval.evals.schemas import DeployEvalJobRequest, StartEvaluationRequest

# Import engines to ensure they are registered
from budeval.registry.engines import opencompass  # noqa: F401


logger = logging.getLogger(__name__)


class EvaluationOpsService:
    """Service for evaluation."""

    @classmethod
    async def verify_cluster_connection(
        cls, verify_cluster_connection_request: StartEvaluationRequest, task_id: str, workflow_id: str
    ):
        """Verify cluster connection."""
        logger.info(f"Verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}")
        k8_handler = KubernetesClusterHandler()
        return k8_handler.verify_cluster_connection(verify_cluster_connection_request.kubeconfig)

    @classmethod
    async def deploy_eval_job(
        cls, evaluate_model_request: DeployEvalJobRequest, task_id: str, workflow_id: str
    ) -> dict:
        """Deploy evaluation job with persistent volumes."""
        logger.info(f"Deploying evaluation job for workflow_id: {workflow_id} and task_id: {task_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Create unique job identifier
            job_uuid = f"eval-{evaluate_model_request.eval_request_id}"
            logger.info(f"Creating job with UUID: {job_uuid}")

            # Get engine metadata for Docker image
            from budeval.registry.engines.core import EngineRegistry

            # Debug: List all registered engines
            registered_engines = EngineRegistry.list_engines()
            logger.info(f"Registered engines: {list(registered_engines.keys())}")

            try:
                engine_metadata = EngineRegistry.get_metadata(evaluate_model_request.engine)
                logger.info(
                    f"Using engine: {evaluate_model_request.engine}, Docker image: {engine_metadata.docker_image_url}"
                )
            except KeyError as e:
                logger.error(f"Engine {evaluate_model_request.engine} not found in registry: {e}")
                logger.error(f"Available engines: {list(registered_engines.keys())}")
                raise ValueError(f"Unsupported engine: {evaluate_model_request.engine}")

            # Prepare engine arguments
            engine_args = {
                "model_name": evaluate_model_request.eval_request_id,
                "api_key": evaluate_model_request.api_key,
                "base_url": evaluate_model_request.base_url,
                "datasets": evaluate_model_request.dataset,
                "engine": evaluate_model_request.engine,
            }
            logger.info(f"Engine arguments prepared: {engine_args}")

            # Deploy job with volumes
            logger.info(
                "Deploying job with volumes - Shared datasets at /workspace/data, Output: 10Gi at /workspace/outputs"
            )
            ansible_orchestrator.run_job_with_volumes(
                runner_type="kubernetes",
                uuid=job_uuid,
                kubeconfig=evaluate_model_request.kubeconfig,
                engine_args=engine_args,
                docker_image=engine_metadata.docker_image_url,
                namespace="budeval",
                ttl_seconds=3600,  # 1 hour TTL
                output_volume_size="10Gi",  # Testing
            )

            logger.info(f"Successfully deployed evaluation job {job_uuid}")
            return {
                "job_id": job_uuid,
                "status": "deployed",
                "namespace": "budeval",
                "data_volume": f"{job_uuid}-data-pv",
                "output_volume": f"{job_uuid}-output-pv",
            }

        except Exception as e:
            logger.error(f"Failed to deploy evaluation job: {e}", exc_info=True)
            raise e

    @classmethod
    async def get_job_status(cls, job_id: str, kubeconfig: Optional[str], namespace: str = "budeval") -> dict:
        """Get the status of a deployed evaluation job."""
        logger.info(f"Getting status for job: {job_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Get job status using Ansible
            status = ansible_orchestrator.get_job_status(job_id, kubeconfig, namespace)

            return {
                "job_id": job_id,
                "status": status.get("status", "unknown"),
                "namespace": namespace,
                "details": status,
            }

        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}", exc_info=True)
            return {"job_id": job_id, "status": "error", "error": str(e)}

    @classmethod
    async def cleanup_job(cls, job_id: str, kubeconfig: Optional[str], namespace: str = "budeval") -> dict:
        """Clean up a deployed evaluation job and its resources."""
        logger.info(f"Cleaning up job: {job_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Clean up job resources
            ansible_orchestrator.cleanup_job_resources(job_id, kubeconfig, namespace)

            return {"job_id": job_id, "status": "cleaned_up", "namespace": namespace}

        except Exception as e:
            logger.error(f"Failed to cleanup job {job_id}: {e}", exc_info=True)
            return {"job_id": job_id, "status": "cleanup_failed", "error": str(e)}


class EvaluationService:
    """Service for evaluation."""

    async def evaluate_model(
        self, evaluate_model_request: StartEvaluationRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Evaluate model.

        Args:
            evaluate_model_request: StartEvaluationRequest

        Returns:
            Union[WorkflowMetadataResponse, ErrorResponse]
        """
        logger.info(f"Model Evaluation Started for workflow_id: {evaluate_model_request.model_name}")

        response: Union[WorkflowMetadataResponse, ErrorResponse]

        from .workflows import EvaluationWorkflow

        try:
            response = await EvaluationWorkflow().__call__(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error evaluating model: {e}", exc_info=True)
            raise ErrorResponse(message=f"Error evaluating model: {e}") from e
        return response
