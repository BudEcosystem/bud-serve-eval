import asyncio
import json
import uuid
from datetime import timedelta
from http import HTTPStatus

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
from budeval.core.schemas import (
    DatasetCategory,
    GenericDatasetConfig,
    GenericEvaluationRequest,
    GenericModelConfig,
    ModelType,
)
from budeval.core.transformers.registry import TransformerRegistry
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
    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def create_engine_config(
        ctx: wf.WorkflowActivityContext,
        evaluate_model_request: str,
    ) -> dict:
        """Create engine-specific configuration using transformers.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow
            evaluate_model_request (str): A JSON string containing the evaluate model request parameters
        """
        logger = logging.getLogger("::EVAL:: Create Engine Config")
        logger.debug(f"Creating engine config for {evaluate_model_request}")

        evaluate_model_request_json = StartEvaluationRequest.model_validate_json(evaluate_model_request)

        response: SuccessResponse | ErrorResponse
        try:
            # TODO: check the none cases, see if the opencompass handles it
            # Convert to generic evaluation request
            generic_request = GenericEvaluationRequest(
                eval_request_id=evaluate_model_request_json.eval_request_id,
                engine=evaluate_model_request_json.engine,
                model=GenericModelConfig(
                    api_version=None,
                    model_path=None,
                    tokenizer_path=None,
                    top_p=None,
                    name=evaluate_model_request_json.model_name,
                    type=ModelType.API,
                    api_key=evaluate_model_request_json.api_key,
                    base_url=evaluate_model_request_json.base_url,
                    temperature=None,
                    max_tokens=None,
                ),
                datasets=[
                    GenericDatasetConfig(
                        name=dataset_name,
                        category=DatasetCategory.CUSTOM,  # Default category
                        version="1.0.0",
                        split="test",
                    )
                    for dataset_name in (evaluate_model_request_json.datasets or [])
                ],
                batch_size=8,
                num_workers=1,
                timeout_minutes=30,
                kubeconfig=evaluate_model_request_json.kubeconfig,
                namespace="budeval",
                debug=True,
            )

            # Get the appropriate transformer
            transformer = TransformerRegistry.get_transformer(generic_request.engine)

            # Transform the request
            transformed = transformer.transform_request(generic_request)

            # Create ConfigMap with transformed configuration
            from .configmap_manager import ConfigMapManager

            configmap_manager = ConfigMapManager(namespace="budeval")

            configmap_result = configmap_manager.create_generic_config_map(
                eval_request_id=str(generic_request.eval_request_id),
                engine=generic_request.engine.value,
                config_files=transformed.config_files,
                kubeconfig=evaluate_model_request_json.kubeconfig,
            )

            logger.info(f"Created {generic_request.engine.value} ConfigMap: {configmap_result['configmap_name']}")
            response = SuccessResponse(
                code=HTTPStatus.CREATED.value,
                message=f"{generic_request.engine.value} configuration created successfully",
                param={
                    **configmap_result,
                    "transformed_data": transformed.model_dump(mode="json"),
                },
            )
        except Exception as e:
            logger.error(f"Error creating engine config: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error creating engine configuration", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def deploy_eval_job(
        ctx: wf.WorkflowActivityContext,
        deploy_request: str,
    ) -> dict:
        """Deploy the evaluation job using transformed configuration.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            deploy_request (str): A JSON string containing the deployment request with transformed data.
        """
        logger = logging.getLogger("::EVAL:: Eval Deployment Job")
        logger.debug(f"Deploying evaluation job with request: {deploy_request}")

        workflow_id = ctx.workflow_id
        task_id = ctx.task_id

        deploy_request_json = json.loads(deploy_request)

        # Extract the original request and transformed data
        evaluate_model_request_json = StartEvaluationRequest.model_validate_json(
            deploy_request_json["evaluate_model_request"]
        )
        transformed_data = deploy_request_json["transformed_data"]

        # Create deployment payload with engine from request
        payload = DeployEvalJobRequest(
            engine=evaluate_model_request_json.engine.value,
            eval_request_id=str(evaluate_model_request_json.eval_request_id),
            api_key=evaluate_model_request_json.api_key,
            base_url=evaluate_model_request_json.base_url,
            kubeconfig=evaluate_model_request_json.kubeconfig,
            dataset=evaluate_model_request_json.datasets or ["mmlu", "gsm8k"],
        )

        logger.debug(f"Deploying evaluation job for engine: {payload.engine}")

        response: SuccessResponse | ErrorResponse
        try:
            # Pass transformed data to the service
            job_details = asyncio.run(
                EvaluationOpsService.deploy_eval_job_with_transformation(
                    payload, transformed_data, task_id, workflow_id
                )
            )

            response = SuccessResponse(message="Evaluation job deployed successfully", param=dict(job_details))
        except Exception as e:
            logger.error(f"Error deploying evaluation job: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error deploying evaluation job", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def verify_cluster_connection(
        ctx: wf.WorkflowActivityContext,
        verify_cluster_connection_request: str,
    ) -> SuccessResponse | ErrorResponse:
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
        task_id = str(ctx.task_id)

        verify_cluster_connection_request_json = StartEvaluationRequest.model_validate_json(
            verify_cluster_connection_request
        )

        try:
            cluster_verified = asyncio.run(
                EvaluationOpsService.verify_cluster_connection(
                    verify_cluster_connection_request_json, task_id, workflow_id
                )
            )

            if cluster_verified:
                return SuccessResponse(
                    code=HTTPStatus.OK.value,
                    message="Cluster connection verified successfully",
                    param={"cluster_verified": cluster_verified},
                ).model_dump(mode="json")
            else:
                return ErrorResponse(
                    code=HTTPStatus.BAD_REQUEST.value, message="Cluster connection verification failed"
                ).model_dump(mode="json")
        except Exception as e:
            error_msg = (
                f"Error verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}, error: {e}"
            )
            logger.error(error_msg)
            return ErrorResponse(message="Cluster connection verification failed", code=HTTPStatus.BAD_REQUEST.value).model_dump(mode="json") # type: ignore # noqa

    @dapr_workflows.register_activity  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
    @staticmethod
    def monitor_eval_job_progress(
        ctx: wf.WorkflowActivityContext,
        monitor_request: str,
    ) -> dict:
        """Monitor the evaluation job progress.

        Args:
            ctx (WorkflowActivityContext): The context of the Dapr workflow, providing
                access to workflow instance information.
            monitor_request (str): A JSON string containing the monitoring request parameters
                including job_id, kubeconfig, and namespace.
        """
        logger = logging.getLogger("::EVAL:: Monitor Job Progress")
        logger.debug(f"Monitoring job progress for {monitor_request}")

        monitor_request_json = json.loads(monitor_request)
        job_id = monitor_request_json["job_id"]
        kubeconfig = monitor_request_json["kubeconfig"]
        namespace = monitor_request_json.get("namespace", "budeval")

        response: SuccessResponse | ErrorResponse
        try:
            job_status = asyncio.run(EvaluationOpsService.get_job_status(job_id, kubeconfig, namespace))

            logger.debug(f"Job status for {job_id}: {job_status}")

            response = SuccessResponse(message="Job status retrieved successfully", param=job_status)
        except Exception as e:
            logger.error(f"Error monitoring job progress: {e}", exc_info=True)
            response = ErrorResponse(
                message="Error monitoring job progress", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        return response.model_dump(mode="json")

    @dapr_workflows.register_workflow  # type: ignore [reportUnknownReturnType,reportArgumentType] # noqa
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
        logger.debug(f"Evaluating model {evaluate_model_request}")

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
                "kubeconfig": evaluate_model_request_json.kubeconfig, # Preference for using in cluster execution
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
        eta_minutes = 30
        notification_req.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=f"{eta_minutes} minutes",
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
            message=f"{25} minutes",
            status=WorkflowStatus.RUNNING,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Create Engine Configuration
        logger.info(f"Creating {evaluate_model_request_json.engine.value} configuration")
        create_config_result = yield ctx.call_activity(
            EvaluationWorkflow.create_engine_config,
            input=evaluate_model_request_json.model_dump_json(),
        )

        logger.debug(f"Engine Configuration Creation Result: {create_config_result}")

        if create_config_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
            logger.error(f"Engine Configuration Creation Failed: {create_config_result.get('message')}")
            # notify that config creation failed
            notification_req.payload.event = "create_engine_config"
            notification_req.payload.content = NotificationContent(
                title="Configuration creation failed",
                message=create_config_result["message"],
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # notify that config creation is successful
        notification_req.payload.event = "create_engine_config"
        configmap_name = create_config_result.get("param", {}).get("configmap_name", "configuration")
        engine_name = evaluate_model_request_json.engine.value
        notification_req.payload.content = NotificationContent(
            title="Configuration created successfully",
            message=f"{engine_name} configuration '{configmap_name}' created for model {evaluate_model_request_json.model_name}",
            status=WorkflowStatus.COMPLETED,
        )
        dapr_workflows.publish_notification(
            workflow_id=instance_id,
            notification=notification_req,
            target_topic_name=evaluate_model_request_json.source_topic,
            target_name=evaluate_model_request_json.source,
        )

        # Deploy Evaluation Job with transformed data
        deploy_request = {
            "evaluate_model_request": evaluate_model_request_json.model_dump_json(),
            "transformed_data": create_config_result.get("param", {}).get("transformed_data", {}),
        }
        deploy_eval_job_result = yield ctx.call_activity(
            EvaluationWorkflow.deploy_eval_job,
            input=json.dumps(deploy_request),
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
        logger.info("Starting job monitoring")

        # Extract job details from deployment result
        job_details = deploy_eval_job_result.get("param", {})
        job_id = job_details.get("job_id")

        if not job_id:
            logger.error("No job_id found in deployment result")
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring failed",
                message="No job ID found to monitor",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return

        # Prepare monitoring request
        monitor_request = {
            "job_id": job_id,
            "kubeconfig": evaluate_model_request_json.kubeconfig,
            "namespace": "budeval",
        }

        # Monitor job until completion
        max_monitoring_attempts = 360  # 30 minutes with 5-second intervals
        monitoring_attempt = 0
        job_completed = False
        final_job_status = None

        while (
            monitoring_attempt < max_monitoring_attempts and not job_completed
        ):  # TODO : Change to proper worflow based on dapr workflow
            monitoring_attempt += 1

            # Wait before checking status (except for first attempt)
            if monitoring_attempt > 1:
                yield ctx.create_timer(timedelta(seconds=5))

            # Check job status
            monitor_result = yield ctx.call_activity(
                EvaluationWorkflow.monitor_eval_job_progress,
                input=json.dumps(monitor_request),
            )

            logger.debug(f"Monitor attempt {monitoring_attempt}: {monitor_result}")

            if monitor_result.get("code", HTTPStatus.OK.value) != HTTPStatus.OK.value:
                logger.warning(f"Monitoring attempt {monitoring_attempt} failed: {monitor_result.get('message')}")
                continue

            job_status_data = monitor_result.get("param", {})
            job_status = job_status_data.get("status", "unknown")
            job_details_info = job_status_data.get("details", {})

            # Check if job is completed (succeeded or failed)
            if job_status in ["completed", "succeeded", "failed", "error"]:
                job_completed = True
                final_job_status = job_status_data
                logger.info(f"Job {job_id} completed with status: {job_status}")
                break

            # Check Kubernetes job status from details
            if job_details_info:
                # Safely convert to int, handling both string and int values
                try:
                    succeeded = int(job_details_info.get("succeeded", 0))
                    failed = int(job_details_info.get("failed", 0))
                except (ValueError, TypeError):
                    # Fallback to 0 if conversion fails
                    succeeded = 0
                    failed = 0

                if succeeded > 0:
                    job_completed = True
                    final_job_status = job_status_data
                    final_job_status["status"] = "succeeded"
                    logger.info(f"Job {job_id} succeeded")
                    break
                elif failed > 0:
                    job_completed = True
                    final_job_status = job_status_data
                    final_job_status["status"] = "failed"
                    logger.info(f"Job {job_id} failed")
                    break

            # Publish progress notification every 10 attempts (50 seconds)
            if monitoring_attempt % 10 == 0:
                notification_req.payload.event = "monitor_eval_job_progress"
                notification_req.payload.content = NotificationContent(
                    title="Job monitoring in progress",
                    message=f"Job {job_id} is still running. Status: {job_status}. Attempt: {monitoring_attempt}/{max_monitoring_attempts}",
                    status=WorkflowStatus.RUNNING,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )

        # Handle monitoring completion
        if job_completed and final_job_status:
            final_status = final_job_status.get("status", "unknown")

            if final_status in ["succeeded", "completed"]:
                # Job succeeded
                notification_req.payload.event = "monitor_eval_job_progress"
                notification_req.payload.content = NotificationContent(
                    title="Job monitoring completed - Success",
                    message=f"Job {job_id} completed successfully",
                    status=WorkflowStatus.COMPLETED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
            else:
                # Job failed
                notification_req.payload.event = "monitor_eval_job_progress"
                notification_req.payload.content = NotificationContent(
                    title="Job monitoring completed - Failed",
                    message=f"Job {job_id} failed with status: {final_status}",
                    status=WorkflowStatus.FAILED,
                )
                dapr_workflows.publish_notification(
                    workflow_id=instance_id,
                    notification=notification_req,
                    target_topic_name=evaluate_model_request_json.source_topic,
                    target_name=evaluate_model_request_json.source,
                )
                return  # Exit workflow on failure
        else:
            # Monitoring timed out
            logger.error(f"Job monitoring timed out after {max_monitoring_attempts} attempts")
            notification_req.payload.event = "monitor_eval_job_progress"
            notification_req.payload.content = NotificationContent(
                title="Job monitoring timed out",
                message=f"Job {job_id} monitoring timed out after {max_monitoring_attempts} attempts",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflows.publish_notification(
                workflow_id=instance_id,
                notification=notification_req,
                target_topic_name=evaluate_model_request_json.source_topic,
                target_name=evaluate_model_request_json.source,
            )
            return  # Exit workflow on timeout

        # END OF WORKFLOW WITH NOTIFICATIONS
        # Result
        notification_req.payload.event = "results"

        # Include actual job results if available
        job_results = {"job_id": job_id}
        if final_job_status:
            job_results.update(final_job_status)

        notification_req.payload.content = NotificationContent(
            title="Model evaluation successful",
            message="Model evaluation completed successfully",
            status=WorkflowStatus.COMPLETED,
            result=job_results,
        )
        workflow_status = check_workflow_status_in_statestore(instance_id)
        if workflow_status:
            # TODO: Delete workflow data from statestore
            # asyncio.run(ClusterOpsService.delete_node_info_from_statestore(str(add_cluster_request_json.id)))
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
        self, request: StartEvaluationRequest, workflow_id: str | None = None
    ) -> WorkflowMetadataResponse | ErrorResponse:
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
                id="preparing_eval_engine",
                title="Preparing Eval Engine",
                description="Warming up eval enfine",
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

        eta = 30 * 60  # 30 minutes estimate for evaluation jobs
        # Schedule the workflow
        try:
            response = await dapr_workflows.schedule_workflow(
                workflow_name="evaluate_model",
                workflow_input=request.model_dump_json(),
                workflow_id=workflow_id,
                workflow_steps=workflow_steps,
                eta=eta,
                target_topic_name=request.source_topic,
                target_name=request.source,
            )
            return response or ErrorResponse(
                message="Failed to schedule workflow", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
        except Exception as e:
            logger.error(f"Error scheduling workflow: {e}", exc_info=True)
            return ErrorResponse(
                message=f"Error scheduling workflow: {e}", code=HTTPStatus.INTERNAL_SERVER_ERROR.value
            )
