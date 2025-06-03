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
from typing import Optional, List

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
        # import asyncio
        # from budeval.evals.volume_init import VolumeInitializer
        # from budeval.evals.engine_preloader import EnginePreloader

        # # Start volume initialization in background if not already initialized
        # volume_init = VolumeInitializer()
        # if not VolumeInitializer._initialized:
        #     logger.info("Starting background volume initialization")
        #     # Create a background task that won't block the request
        #     asyncio.create_task(volume_init.ensure_eval_datasets_volume())

        # # Start engine preloading in background if not already initialized
        # engine_preloader = EnginePreloader()
        # if not EnginePreloader.is_initialized():
        #     logger.info("Starting background engine preloading")
        #     # Create a background task that won't block the request
        #     asyncio.create_task(engine_preloader.preload_all_engines())

        # Proceed with evaluation request immediately
        response = await EvaluationService().evaluate_model(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save evaluation request: {str(e)}") from e


@evals_routes.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)"),
):
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
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}") from e


@evals_routes.delete("/cleanup/{job_id}")
async def cleanup_job(
    job_id: str,
    kubeconfig: Optional[str] = Query(None, description="Kubernetes configuration as JSON string (optional)"),
):
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
        raise HTTPException(status_code=500, detail=f"Failed to cleanup job: {str(e)}") from e


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
        raise HTTPException(status_code=500, detail=f"Failed to initialize volume: {str(e)}") from e


@evals_routes.post("/preload-engines")
async def preload_engines(engine_names: Optional[List[str]] = None):
    """Manually preload evaluation engine Docker images.

    Args:
        engine_names (Optional[List[str]]): Specific engine names to preload. If None, preloads all engines.

    Returns:
        dict: Engine preloading result
    """
    try:
        from budeval.evals.engine_preloader import EnginePreloader

        engine_preloader = EnginePreloader()

        if engine_names:
            await engine_preloader.preload_specific_engines(engine_names)
            message = f"Specific engines preloaded: {engine_names}"
        else:
            await engine_preloader.preload_all_engines()
            message = "All evaluation engines preloaded"

        return {
            "status": "success",
            "message": message,
            "preloaded_engines": list(EnginePreloader.get_preloaded_engines()),
        }
    except Exception as e:
        logger.error(f"Failed to preload engines: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preload engines: {str(e)}") from e


@evals_routes.get("/engine-status")
async def get_engine_status():
    """Get the status of engine preloading.

    Returns:
        dict: Engine preloading status information
    """
    try:
        from budeval.evals.engine_preloader import EnginePreloader
        from budeval.registry.engines.core import EngineRegistry

        # Get all registered engines
        registered_engines = EngineRegistry.list_engines()

        # Get preloaded engines
        preloaded_engines = EnginePreloader.get_preloaded_engines()

        # Calculate status
        engine_status = {}
        for engine_name, metadata in registered_engines.items():
            engine_status[engine_name] = {
                "preloaded": EnginePreloader.is_engine_preloaded(engine_name),
                "docker_image": metadata.docker_image_url,
                "version": metadata.version,
                "description": metadata.description,
            }

        return {
            "initialized": EnginePreloader.is_initialized(),
            "total_engines": len(registered_engines),
            "preloaded_count": len(preloaded_engines),
            "engines": engine_status,
        }
    except Exception as e:
        logger.error(f"Failed to get engine status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get engine status: {str(e)}") from e


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
            dataset=["dataset1"],  # Default dataset
        )

        # Deploy the job
        response = await EvaluationOpsService.deploy_eval_job(
            deploy_request, task_id="test-task", workflow_id="test-workflow"
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deploy test job: {str(e)}") from e
