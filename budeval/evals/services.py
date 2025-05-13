from typing import Union

from budmicroframe.commons.schemas import ErrorResponse, WorkflowMetadataResponse

from budeval.commons.base_crud import SessionMixin
from budeval.commons.logging import logging
from budeval.evals.kubernetes import KubernetesClusterHandler
from budeval.evals.schemas import StartEvaluationRequest


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
    async def evaluate_model(
        cls, evaluate_model_request: StartEvaluationRequest, task_id: str, workflow_id: str
    ):
        """Evaluate model."""
        logger.info(f"Evaluating model for workflow_id: {workflow_id} and task_id: {task_id}")
        # TODO: Implement model evaluation
        return

class EvaluationService:
    """Service for evaluation."""

    async def evaluate_model(self, evaluate_model_request: StartEvaluationRequest) -> Union[WorkflowMetadataResponse, ErrorResponse]:
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
