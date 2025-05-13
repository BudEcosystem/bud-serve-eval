from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase
from pydantic import Field


class EvaluationRequest(CloudEventBase):
    """Schema for evaluation request."""

    eval_request_id: UUID = Field(..., description="Unique identifier for the evaluation request")
    model_name: str = Field(..., description="Name of the model to be evaluated")
    api_key: str = Field(..., description="API key for authentication")
    base_url: str = Field(..., description="Base URL for the model API")
    kubeconfig: str = Field(..., description="Kubernetes configuration JSON content")

    class Config: #noqa
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
    kubeconfig: str = Field(..., description="Kubernetes configuration JSON content")

    class Config: #noqa
        json_schema_extra = {
            "example": {
                "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "model_name": "gpt-4",
                "api_key": "sk-...",
                "base_url": "https://api.openai.com/v1",
                "kubeconfig": "<Kubernetes config JSON content>",
            }
        }

