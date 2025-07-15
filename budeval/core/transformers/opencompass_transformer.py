"""OpenCompass-specific transformer implementation."""

import json
from typing import Any, Dict, List, Tuple

from budeval.commons.logging import logging
from budeval.core.schemas import (
    EvaluationEngine,
    GenericEvaluationRequest,
    ModelType,
    TransformedEvaluationData,
)
from budeval.core.transformers.base import BaseTransformer


logger = logging.getLogger(__name__)


class OpenCompassTransformer(BaseTransformer):
    """Transformer for OpenCompass evaluation engine."""

    # Dataset mapping from generic names to OpenCompass names
    DATASET_MAPPING = {
        # Knowledge datasets
        "mmlu": "mmlu",
        "cmmlu": "cmmlu",
        "c_eval": "ceval",

        # Math datasets
        "gsm8k": "gsm8k",
        "math": "math",

        # Reasoning datasets
        "bbh": "bbh",
        "arc": "arc",
        "hellaswag": "hellaswag",

        # Language datasets
        "humaneval": "humaneval",
        "mbpp": "mbpp",

        # Add more mappings as needed
    }

    def __init__(self, engine: EvaluationEngine = EvaluationEngine.OPENCOMPASS):
        """Initialize OpenCompass transformer."""
        super().__init__(engine)

    def transform_request(self, request: GenericEvaluationRequest) -> TransformedEvaluationData:
        """Transform generic request to OpenCompass-specific format."""
        # Validate the request
        self.validate_request(request)

        # Generate configuration files
        config_files = self.generate_config_files(request)

        # Create job configuration
        job_config = self.create_job_config(request)

        return TransformedEvaluationData(
            engine=self.engine,
            job_config=job_config,
            config_files=config_files,
            metadata={
                "model_name": request.model.name,
                "datasets": [d.name for d in request.datasets],
                "eval_request_id": str(request.eval_request_id),
            }
        )

    def generate_config_files(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Generate OpenCompass configuration files."""
        config_files = {}

        # Generate model configuration
        config_files["bud-model.py"] = self._generate_model_config(request)

        # Generate dataset configuration
        config_files["bud-datasets.py"] = self._generate_dataset_config(request)

        # Generate main evaluation configuration
        config_files["eval_config.py"] = self._generate_eval_config(request)

        # Generate metadata
        config_files["metadata.json"] = json.dumps({
            "eval_request_id": str(request.eval_request_id),
            "model_name": request.model.name,
            "datasets": [d.name for d in request.datasets],
            "engine": self.engine.value,
        }, indent=2)

        return config_files

    def _generate_model_config(self, request: GenericEvaluationRequest) -> str:
        """Generate OpenCompass model configuration."""
        model = request.model

        # Extract parameters
        max_out_len = model.extra_params.get("max_out_len", model.max_tokens or 2048)
        max_seq_len = model.extra_params.get("max_seq_len", 4096)
        batch_size = request.batch_size
        query_per_second = model.extra_params.get("query_per_second", 1)

        if model.type == ModelType.API:
            config = f"""from opencompass.models import OpenAI

models = [
    dict(
        abbr='{request.eval_request_id}',
        type=OpenAI,
        path='{model.name}',
        key='{model.api_key}',
        query_per_second={query_per_second},
        max_out_len={max_out_len},
        max_seq_len={max_seq_len},
        openai_api_base='{model.base_url}',
        batch_size={batch_size}),
]
"""
        else:
            # For local models, we'd use different OpenCompass model types
            raise NotImplementedError(f"Model type {model.type} not yet implemented for OpenCompass")

        logger.info(f"Generated OpenCompass model config for: {model.name}")
        return config

    def _generate_dataset_config(self, request: GenericEvaluationRequest) -> str:
        """Generate OpenCompass dataset configuration."""
        dataset_list = []

        for dataset in request.datasets:
            # Map generic dataset name to OpenCompass name
            oc_dataset_name = self.get_dataset_mapping(dataset.name)

            # Add _gen suffix for generation-based evaluation if not present
            if not oc_dataset_name.endswith('_gen'):
                oc_dataset_name = f"{oc_dataset_name}_gen"

            dataset_list.append(f"'{oc_dataset_name}'")

        config = f"""# Dataset configuration
from opencompass.datasets import *

# Use predefined dataset configurations
datasets = [{', '.join(dataset_list)}]
"""

        logger.info(f"Generated OpenCompass dataset config with datasets: {dataset_list}")
        return config

    def _generate_eval_config(self, request: GenericEvaluationRequest) -> str:
        """Generate main OpenCompass evaluation configuration."""
        config = f"""# Main evaluation configuration
from mmengine.config import read_base

# Read the model and dataset configurations
with read_base():
    from .bud_model import models
    from .bud_datasets import datasets

# Evaluation configuration
eval = dict(
    partitioner=dict(
        type='NaivePartitioner',
        num_gpus=1
    ),
    runner=dict(
        type='LocalRunner',
        task=dict(type='OpenICLInferTask'),
        max_num_workers={request.num_workers}
    ),
)

# Work directory will be set via command line
"""

        return config

    def build_command(self, request: GenericEvaluationRequest) -> Tuple[List[str], List[str]]:
        """Build OpenCompass command and arguments."""
        logger.info("OpenCompassTransformer.build_command called!")
        command = ["/bin/bash", "-c"]

        # Build the bash script that will:
        # 1. Copy configs to the right location
        # 2. Run OpenCompass with the correct arguments
        datasets_str = " ".join([self.get_dataset_mapping(d.name) for d in request.datasets])

        script = f"""
# Copy configuration files to OpenCompass config directory
mkdir -p /workspace/opencompass/configs/models/bud/
cp /workspace/configs/bud-model.py /workspace/opencompass/configs/models/bud/
cp /workspace/configs/*.py /workspace/opencompass/configs/

# Change to workspace directory where OpenCompass is installed
cd /workspace

# Run OpenCompass evaluation
python /workspace/run.py \\
    --models bud-model \\
    --datasets {datasets_str}_gen \\
    --work-dir /workspace/outputs \\
    {"--debug" if request.debug else ""}
"""

        args = [script.strip()]

        return command, args

    def get_docker_image(self) -> str:
        """Get OpenCompass Docker image."""
        return "ghcr.io/rahulvramesh/opencompass:latest"

    def get_volume_mounts(self) -> List[Dict[str, Any]]:
        """Get volume mounts for OpenCompass."""
        return [
            {
                "name": "datasets",
                "mountPath": "/workspace/data",
                "readOnly": True,
                "claimName": "eval-datasets-pvc",
            },
            {
                "name": "cache",
                "mountPath": "/workspace/cache",
                "type": "emptyDir",
            }
        ]

    def get_environment_variables(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Get environment variables for OpenCompass."""
        env_vars = {
            "HF_HOME": "/workspace/cache/huggingface",
            "TRANSFORMERS_CACHE": "/workspace/cache/transformers",
            "TORCH_HOME": "/workspace/cache/torch",
            "ENGINE_ARGS": json.dumps(request.model.extra_params),
        }

        # Add any additional environment variables from the request
        if "env_vars" in request.extra_params:
            env_vars.update(request.extra_params["env_vars"])

        return env_vars

    def validate_request(self, request: GenericEvaluationRequest) -> None:
        """Validate that the request is compatible with OpenCompass."""
        # Check if model type is supported
        if request.model.type not in [ModelType.API]:
            raise ValueError(f"OpenCompass transformer currently only supports API models, got {request.model.type}")

        # Check if API model has required fields
        if request.model.type == ModelType.API:
            if not request.model.api_key:
                raise ValueError("API key is required for API models")
            if not request.model.base_url:
                raise ValueError("Base URL is required for API models")

        # Check if datasets are supported
        unsupported = []
        for dataset in request.datasets:
            if dataset.name.lower() not in self.DATASET_MAPPING:
                unsupported.append(dataset.name)

        if unsupported:
            logger.warning(f"The following datasets may not be supported by OpenCompass: {unsupported}")

    def get_supported_datasets(self) -> List[str]:
        """Get list of datasets supported by OpenCompass."""
        return list(self.DATASET_MAPPING.keys())

    def get_dataset_mapping(self, dataset_name: str) -> str:
        """Map generic dataset name to OpenCompass-specific name."""
        return self.DATASET_MAPPING.get(dataset_name.lower(), dataset_name.lower())
