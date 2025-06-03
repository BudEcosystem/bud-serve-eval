from typing import List, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import BaseModel, Field


class EvaluationRequest(CloudEventBase):
    """Schema for evaluation request."""

    eval_request_id: UUID = Field(..., description="Unique identifier for the evaluation request")
    model_name: str = Field(..., description="Name of the model to be evaluated")
    api_key: str = Field(..., description="API key for authentication")
    base_url: str = Field(..., description="Base URL for the model API")
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "model_name": "gpt-4",
                "api_key": "sk-...",
                "base_url": "https://api.openai.com/v1",
                "kubeconfig": "<Kubernetes config JSON content>",
            }
        }


# Workflow Schemas
class StartEvaluationRequest(CloudEventBase):
    """Schema for start evaluation request."""

    eval_request_id: UUID = Field(..., description="Unique identifier for the evaluation request")
    model_name: str = Field(..., description="Name of the model to be evaluated")
    api_key: str = Field(..., description="API key for authentication")
    base_url: str = Field(..., description="Base URL for the model API")
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "model_name": "gpt-4",
                "api_key": "sk-...",
                "base_url": "https://api.openai.com/v1",
                "kubeconfig": "<Kubernetes config JSON content>",
            }
        }


class DeployEvalJobRequest(BaseModel):
    """Schema for deploy evaluation job request."""

    engine: str = Field(..., description="Engine to use for the evaluation job")
    eval_request_id: str = Field(..., description="Unique identifier for the job")
    kubeconfig: Optional[str] = Field(
        None, description="Kubernetes configuration JSON content (optional, uses local config if not provided)"
    )
    api_key: str = Field(..., description="API key for authentication")
    base_url: str = Field(..., description="Base URL for the model API")
    dataset: List[str] = Field(..., description="Datasets to evaluate on")

    class Config:  # noqa
        json_schema_extra = {
            "example": {
                "engine": "OpenCompass",
                "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "api_key": "sk-...",
                "base_url": "https://api.openai.com/v1",
                "kubeconfig": "<Kubernetes config JSON content>",
                "dataset": ["dataset1"],
            }
        }


# Job Schemas
class VolumeMount(BaseModel):
    name: str = Field(..., description="Name of the volume")
    claim_name: str = Field(..., description="Name of the PVC to use")
    mount_path: str = Field(..., description="Path to mount in the container")


class Job(BaseModel):
    # Existing fields...

    # Volume mount configurations
    read_only_mounts: Optional[List[VolumeMount]] = Field(None, description="Read-only volume mounts for the job")
    writable_mounts: Optional[List[VolumeMount]] = Field(None, description="Writable volume mounts for the job")

    class Config:  # noqa
        schema_extra = {
            "example": {
                # Existing example fields...
                "read_only_mounts": [
                    {"name": "datasets-volume", "claim_name": "datasets-pvc", "mount_path": "/data/datasets"}
                ],
                "writable_mounts": [
                    {"name": "results-volume", "claim_name": "results-pvc", "mount_path": "/data/results"}
                ],
            }
        }
