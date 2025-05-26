import asyncio
import json
import uuid
from datetime import timedelta
from http import HTTPStatus
from typing import Optional, Union

import dapr.ext.workflow as wf
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    ErrorResponse,
    NotificationContent,
    NotificationRequest,
    SuccessResponse,
    WorkflowMetadataResponse,
    WorkflowStep,
)
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from budeval.commons.logging import logging
from budeval.commons.utils import check_workflow_status_in_statestore, update_workflow_data_in_statestore
from budeval.evals.schemas import DeployEvalJobRequest, StartEvaluationRequest
from budeval.evals.services import EvaluationOpsService


logger = logging.getLogger(__name__)


# Worflow
dapr_workflows = DaprWorkflow()

# Retry Policy
retry_policy = wf.RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=1,
    backoff_coefficient=1,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)


# EvaluationWorkflow
class EvaluationWorkflow:

    # Activities
    @dapr_workflows.register_activity
    @staticmethod
    def deploy_eval_job(
        ctx: wf.WorkflowActivityContext,
        evaluate_model_request: str,
    ) -> dict:
        """Deploy the evaluation job.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            evaluate_model_request (str): A JSON string containing the evaluate model request parameters
                including model name, API key, and cluster configuration.
        """
        logger = logging.getLogger("::EVAL:: Eval Deployment Job")
        logger.debug(f"Deploying evaluation job for {evaluate_model_request}")

        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)
        payload = DeployEvalJobRequest(
           engine="OpenCompass",
           eval_request_id=str(evaluate_model_request_json.eval_request_id),
           api_key=evaluate_model_request_json.api_key,
           base_url=evaluate_model_request_json.base_url,
           kubeconfig=evaluate_model_request_json.kubeconfig,
           dataset=["dataset1"] #TODO: Make this from the request
        )

        logger.debug(f"Deploying evaluation job for {payload}")

        response: Union[SuccessResponse, ErrorResponse]
        try:

            job_details = asyncio.run(
                EvaluationOpsService.deploy_eval_job(
                    payload, task_id, workflow_id
                )
            )

            response = SuccessResponse(
                message="Evaluation job deployed successfully",
                param=dict(job_details)
            )
        except Exception as e:
            logger.error(f"Error deploying evaluation job: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error deploying evaluation job",
                code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity
    @staticmethod
    def verify_cluster_connection(
        ctx: wf.WorkflowActivityContext,
        verify_cluster_connection_request: str,
    ) -> dict:
        """Verify the cluster connection.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            verify_cluster_connection_request (str): A JSON string containing the verify cluster connection request parameters
                including model name, API key, and cluster configuration.
        """
        logger = logging.getLogger("::EVAL:: VerifyClusterConnectionActivity")
        logger.debug(f"Verifying cluster connection for {verify_cluster_connection_request}")

        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        verify_cluster_connection_request_json = StartEvaluationRequest.model_validate_json(verify_cluster_connection_request)

        response: Union[SuccessResponse, ErrorResponse]
        try:
            cluster_verified = asyncio.run(
                EvaluationOpsService.verify_cluster_connection(
                    verify_cluster_connection_request_json, task_id, workflow_id
                )
            )

            if cluster_verified:
                response = SuccessResponse(
                    message="Cluster connection verified successfully", param={"cluster_verified": cluster_verified}
                )
            else:
                response = ErrorResponse(
                    message="Cluster connection verification failed", code=HTTPStatus.BAD_REQUEST.value
                )
        except Exception as e:
            error_msg = (
                f"Error verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            response = ErrorResponse(
                message="Cluster connection verification failed", code=HTTPStatus.BAD_REQUEST.value
            )
        return response.model_dump(mode="json")


    @dapr_workflows.register_workflow
    @staticmethod
    def evaluate_model(ctx: wf.DaprWorkflowContext, evaluate_model_request: str):
        """Execute the workflow to evaluate a model.

        This workflow verifies the cluster connection, deploys an evaluation job, and monitors its progress.

        Args:
            ctx (DaprWorkflowContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            evaluate_model_request (str): A JSON string containing the evaluation request parameters
                including model name, API key, and cluster configuration.
        """
        logger = logging.getLogger("::EVAL:: EvaluateModelWorkflow")
        logger.debug(
            f"Evaluating model {evaluate_model_request}"
        )

        instance_id = str(ctx.instance_id)
        logger.info(f"Evaluating model for instance_id: {instance_id}")

        # Parse the request
        try:
            evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error parsing cluster create request: {e}", exc_info=True)
            return

        # Set workflow data
        update_workflow_data_in_statestore(
            instance_id,
            {
                "model_name": evaluate_model_request_json.model_name,
                "eval_request_id": str(evaluate_model_request_json.eval_request_id),
                "api_key": evaluate_model_request_json.api_key,
                "base_url": evaluate_model_request_json.base_url,
                "kubeconfig": evaluate_model_request_json.kubeconfig,
            },
        )

        # Notifications
        # Set up notification
        workflow_name = "evaluate_model"

        # Notification Request
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=evaluate_model_request_json, name=workflow_name, workflow_id=instance_id
        )
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "evaluation_status"
        notification_req.payload.content = NotificationContent(
            title="Model evaluation process is initiated",
            message=f"Model evaluation process is initiated for {evaluate_model_request_json.model_name}",
            status=WorkflowStatus.STARTED,
        )

        # Publish initial notification
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Set initial ETA
        notification_req.payload.event = "eta"
        eta_minutes = 10
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta_minutes*10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # End Of Notifications
        logger.info("Starting Cluster Connection Verification")
        verify_cluster_connection_result = yield ctx.call_activity(
                EvaluationWorkflow.verify_cluster_connection,
                input=evaluate_model_request_json.model_dump_json(),
            )

        logger.debug(f"Cluster Connection Verification Result: {verify_cluster_connection_result}")

        if verify_cluster_connection_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.error(f"Cluster Connection Verification Failed: {verify_cluster_connection_result.get('message')}")
            # notify activity that cluster verification failed
            notification_req.payload.event = "verify_cluster_connection"
            notification_req.payload.content = NotificationContent(
                title="Cluster verification failed",
                message=verify_cluster_connection_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # notify activity that cluster verification is successful
        notification_req.payload.event = "verify_cluster_connection"
        notification_req.payload.content = NotificationContent(
            title="Cluster verification successful",
            message=verify_cluster_connection_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )


        # notify activity ETA
        notification_req.payload.event = "eta"
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{2*10}",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Deploy Evaluation Job
        deploy_eval_job_result = yield ctx.call_activity(
            EvaluationWorkflow.deploy_eval_job,
            input=evaluate_model_request_json.model_dump_json(),
        )

        logger.debug(f"Deploy Evaluation Job Result: {deploy_eval_job_result}")

        if deploy_eval_job_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.error(f"Deploy Evaluation Job Failed: {deploy_eval_job_result.get('message')}")
            # notify activity that deploy evaluation job failed
            notification_req.payload.event = "deploy_eval_job"
            notification_req.payload.content = NotificationContent(
                title="Deploy evaluation job failed",
                message=deploy_eval_job_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # notify activity that deploy evaluation job is successful
        notification_req.payload.event = "deploy_eval_job"
        notification_req.payload.content = NotificationContent(
            title="Deploy evaluation job successful",
            message=deploy_eval_job_result["message"],
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Monitor Evaluation Job Progress





        # END OF WORKFLOW WITH NOTIFICATIONS
        # Result
        notification_req.payload.event = "results"
        notification_req.payload.content = NotificationContent(
            title="Model evaluation successful",
            message="Model evaluation completed successfully",
            status=WorkflowStatus.COMPLETED,
            result= {"dummy_key": "dummy_value"}
        )
        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            # TODO: Delete workflow data from statestore
            #asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(add_cluster_request_json.id)))
            return workflow_status
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )
        # yield ctx.call_activity(notify_activity, input=notification_activity_request.model_dump_json())

        notification_req.payload.event = "evaluation_status"
        notification_req.payload.content = NotificationContent(
            title="Model evaluation successful",
            message=f"Model {evaluate_model_request_json.model_name} was evaluated successfully and is now available.",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        return

    async def __call__(
        self, request: StartEvaluationRequest, workflow_id: Optional[str] = None
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Evaluate a model with the given name."""
        logger = logging.getLogger("::EVAL:: EvaluateModelCall")
        workflow_id = str(workflow_id or uuid.uuid4())

        logger.info(f"Evaluating model {request.model_name} for request {request.eval_request_id}")
        workflow_steps = [
            WorkflowStep(
                id="verify_cluster_connection",
                title="Verifying Cluster Connection",
                description="Verify if the cluster is reachable",
            ),
            WorkflowStep(
                id="deploy_eval_job",
                title="Deploying Evaluation Job",
                description="Deploy the evaluation job to the cluster",
            ),
            WorkflowStep(
                id="monitor_eval_job_progress",
                title="Monitoring Evaluation Job Progress",
                description="Monitor the progress of the evaluation job",
            ),
        ]

        eta = 30 * 5  # Estimate should be dynamic
        # Schedule the workflow
        response = await dapr_workflows.schedule_workflow(
            workflow_name="evaluate_model",
            workflow_input=request.model_dump_json(),
            workflow_id=workflow_id,
            workflow_steps=workflow_steps,
            eta=eta,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response
