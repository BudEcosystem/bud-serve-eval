#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

from budmicroframe.commons import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from budeval.evals.services import EvaluationService, EvaluationOpsService

from .schemas import EvaluationRequest


logger = logging.get_logger(__name__)

evals_routes = APIRouter(prefix="/evals", tags=["Evals"])

@evals_routes.post("/start")
async def start_eval(request: EvaluationRequest):
    """Start an evaluation.

    Args:
        request (EvaluationRequest): The evaluation request.

    Returns:
        dict: A simple hello world message
    """
    try:
        from budeval.evals.volume_init import VolumeInitializer

        volume_init = VolumeInitializer()
        await volume_init.ensure_eval_datasets_volume()

        response = await EvaluationService().evaluate_model(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save evaluation request: {str(e)}"
        ) from e

@evals_routes.get("/status/{job_id}")
async def get_job_status(job_id: str, kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)")):
    """Get the status of an evaluation job.

    Args:
        job_id (str): The unique identifier of the job.
        kubeconfig (Optional[str]): Kubernetes configuration as JSON string (optional, uses in-cluster config if not provided).

    Returns:
        dict: Job status information
    """
    try:
        response = await EvaluationOpsService.get_job_status(job_id, kubeconfig)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        ) from e

@evals_routes.delete("/cleanup/{job_id}")
async def cleanup_job(job_id: str, kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)")):
    """Clean up an evaluation job and its resources.

    Args:
        job_id (str): The unique identifier of the job.
        kubeconfig (Optional[str]): Kubernetes configuration as JSON string (optional, uses in-cluster config if not provided).

    Returns:
        dict: Cleanup status information
    """
    try:
        response = await EvaluationOpsService.cleanup_job(job_id, kubeconfig)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup job: {str(e)}"
        ) from e

@evals_routes.post("/init-volume")
async def init_volume():
    """Manually initialize the eval-datasets volume."""
    try:
        from budeval.evals.volume_init import VolumeInitializer
        
        volume_init = VolumeInitializer()
        await volume_init.ensure_eval_datasets_volume()
        
        return {"status": "success", "message": "Volume initialization completed"}
    except Exception as e:
        logger.error(f"Failed to initialize volume: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize volume: {str(e)}"
        ) from e

@evals_routes.post("/test-deploy")
async def test_deploy_job(request: dict):
    """Test endpoint to deploy a job with volumes using the provided payload format.

    Args:
        request (dict): The test request payload.

    Returns:
        dict: Job deployment result
    """
    try:
        # Convert the test payload to DeployEvalJobRequest format
        from budeval.evals.schemas import DeployEvalJobRequest
        
        deploy_request = DeployEvalJobRequest(
            engine="OpenCompass",  # Default engine
            eval_request_id=request.get("eval_request_id", "test-job"),
            kubeconfig=request.get("kubeconfig", "{}"),
            api_key=request.get("api_key", ""),
            base_url=request.get("base_url", ""),
            dataset=["dataset1"]  # Default dataset
        )
        
        # Deploy the job
        response = await EvaluationOpsService.deploy_eval_job(
            deploy_request, 
            task_id="test-task", 
            workflow_id="test-workflow"
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deploy test job: {str(e)}"
        ) from e
