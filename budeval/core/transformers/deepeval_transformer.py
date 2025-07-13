"""DeepEval-specific transformer implementation (example)."""

import json
from typing import Any, Dict, List, Tuple

from budeval.commons.logging import logging
from budeval.core.schemas import (
    DatasetCategory,
    EvaluationEngine,
    GenericEvaluationRequest,
    ModelType,
    TransformedEvaluationData,
)
from budeval.core.transformers.base import BaseTransformer


logger = logging.getLogger(__name__)


class DeepEvalTransformer(BaseTransformer):
    """Transformer for DeepEval evaluation engine.
    
    This is an example implementation showing how to add support
    for additional evaluation engines like DeepEval.
    """
    
    # Dataset mapping from generic names to DeepEval test types
    DATASET_MAPPING = {
        # Reasoning and safety
        "bias": "bias",
        "toxicity": "toxicity",
        "hallucination": "hallucination",
        
        # Quality metrics
        "coherence": "coherence",
        "relevance": "relevance",
        "faithfulness": "faithfulness",
        
        # Task-specific
        "summarization": "summarization",
        "question_answering": "answer_relevancy",
        
        # Custom metrics
        "custom": "custom",
    }
    
    def __init__(self):
        """Initialize DeepEval transformer."""
        super().__init__(EvaluationEngine.DEEPEVAL)
    
    def transform_request(self, request: GenericEvaluationRequest) -> TransformedEvaluationData:
        """Transform generic request to DeepEval-specific format."""
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
                "metrics": [d.name for d in request.datasets],  # In DeepEval, datasets are metrics
                "eval_request_id": str(request.eval_request_id),
            }
        )
    
    def generate_config_files(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Generate DeepEval configuration files."""
        config_files = {}
        
        # Generate test configuration
        config_files["test_config.py"] = self._generate_test_config(request)
        
        # Generate model configuration
        config_files["model_config.json"] = self._generate_model_config(request)
        
        # Generate run script
        config_files["run_evaluation.py"] = self._generate_run_script(request)
        
        # Generate metadata
        config_files["metadata.json"] = json.dumps({
            "eval_request_id": str(request.eval_request_id),
            "model_name": request.model.name,
            "metrics": [d.name for d in request.datasets],
            "engine": self.engine.value,
        }, indent=2)
        
        return config_files
    
    def _generate_test_config(self, request: GenericEvaluationRequest) -> str:
        """Generate DeepEval test configuration."""
        metrics_list = []
        
        for dataset in request.datasets:
            metric_name = self.get_dataset_mapping(dataset.name)
            
            # Map to DeepEval metric classes
            if metric_name == "bias":
                metrics_list.append("BiasMetric(threshold=0.5)")
            elif metric_name == "toxicity":
                metrics_list.append("ToxicityMetric(threshold=0.5)")
            elif metric_name == "hallucination":
                metrics_list.append("HallucinationMetric(threshold=0.5)")
            elif metric_name == "coherence":
                metrics_list.append("GEval(name='Coherence', criteria='Coherence')")
            elif metric_name == "relevance":
                metrics_list.append("GEval(name='Relevance', criteria='Relevance')")
            elif metric_name == "faithfulness":
                metrics_list.append("FaithfulnessMetric(threshold=0.5)")
            elif metric_name == "answer_relevancy":
                metrics_list.append("AnswerRelevancyMetric(threshold=0.5)")
            else:
                # Custom metric
                metrics_list.append(f"GEval(name='{metric_name}', criteria='{metric_name}')")
        
        config = f"""# DeepEval test configuration
from deepeval import assert_test
from deepeval.metrics import (
    BiasMetric, ToxicityMetric, HallucinationMetric,
    GEval, FaithfulnessMetric, AnswerRelevancyMetric
)
from deepeval.test_case import LLMTestCase

# Define metrics to evaluate
metrics = [
    {',\n    '.join(metrics_list)}
]

# Test function will be called by the runner
def run_evaluation(model_client, test_data):
    results = []
    for test_case in test_data:
        llm_test_case = LLMTestCase(
            input=test_case.get('input'),
            actual_output=model_client.generate(test_case.get('input')),
            expected_output=test_case.get('expected_output'),
            context=test_case.get('context', [])
        )
        
        for metric in metrics:
            metric.measure(llm_test_case)
            results.append({{
                'metric': metric.name,
                'score': metric.score,
                'reason': metric.reason
            }})
    
    return results
"""
        
        return config
    
    def _generate_model_config(self, request: GenericEvaluationRequest) -> str:
        """Generate DeepEval model configuration JSON."""
        model = request.model
        
        config = {
            "model_name": model.name,
            "model_type": model.type.value,
            "parameters": {
                "temperature": model.temperature,
                "max_tokens": model.max_tokens,
                "top_p": model.top_p,
            }
        }
        
        if model.type == ModelType.API:
            config["api_config"] = {
                "api_key": model.api_key,
                "base_url": model.base_url,
                "api_version": model.api_version,
            }
        
        return json.dumps(config, indent=2)
    
    def _generate_run_script(self, request: GenericEvaluationRequest) -> str:
        """Generate the main run script for DeepEval."""
        script = f"""#!/usr/bin/env python3
# Main runner script for DeepEval evaluation

import json
import os
from pathlib import Path

# Import test configuration
from test_config import run_evaluation

# Load model configuration
with open('model_config.json', 'r') as f:
    model_config = json.load(f)

# Initialize model client based on configuration
if model_config['model_type'] == 'api':
    from deepeval.models import OpenAIModel
    model_client = OpenAIModel(
        model=model_config['model_name'],
        api_key=model_config['api_config']['api_key'],
        base_url=model_config['api_config']['base_url']
    )
else:
    raise NotImplementedError(f"Model type {{model_config['model_type']}} not implemented")

# Load test data
test_data_path = Path('/workspace/data/deepeval_test_data.json')
if test_data_path.exists():
    with open(test_data_path, 'r') as f:
        test_data = json.load(f)
else:
    # Use default test data
    test_data = [
        {{"input": "What is the capital of France?", "expected_output": "Paris"}},
        {{"input": "Explain quantum computing", "context": ["quantum physics", "computing"]}}
    ]

# Run evaluation
results = run_evaluation(model_client, test_data)

# Save results
output_dir = Path('/workspace/outputs')
output_dir.mkdir(exist_ok=True)

with open(output_dir / 'evaluation_results.json', 'w') as f:
    json.dump({{
        'eval_request_id': '{request.eval_request_id}',
        'model': model_config['model_name'],
        'results': results
    }}, f, indent=2)

print("Evaluation completed successfully!")
"""
        
        return script
    
    def build_command(self, request: GenericEvaluationRequest) -> Tuple[List[str], List[str]]:
        """Build DeepEval command and arguments."""
        command = ["/bin/bash", "-c"]
        
        script = f"""
# Copy configuration files to working directory
cp /workspace/configs/* .

# Install DeepEval if not present
pip install deepeval

# Run the evaluation
python run_evaluation.py
"""
        
        args = [script.strip()]
        
        return command, args
    
    def get_docker_image(self) -> str:
        """Get DeepEval Docker image."""
        # This is a hypothetical image - in practice you'd build one with DeepEval pre-installed
        return "deepeval/deepeval:latest"
    
    def get_volume_mounts(self) -> List[Dict[str, Any]]:
        """Get volume mounts for DeepEval."""
        return [
            {
                "name": "test-data",
                "mountPath": "/workspace/data",
                "readOnly": True,
                "claimName": "eval-datasets-pvc",
            },
            {
                "name": "cache",
                "mountPath": "/workspace/.cache",
                "type": "emptyDir",
            }
        ]
    
    def get_environment_variables(self, request: GenericEvaluationRequest) -> Dict[str, str]:
        """Get environment variables for DeepEval."""
        env_vars = {
            "DEEPEVAL_CACHE_DIR": "/workspace/.cache/deepeval",
        }
        
        # Add API keys if needed
        if request.model.type == ModelType.API:
            if "openai" in request.model.base_url.lower():
                env_vars["OPENAI_API_KEY"] = request.model.api_key
        
        return env_vars
    
    def validate_request(self, request: GenericEvaluationRequest) -> None:
        """Validate that the request is compatible with DeepEval."""
        # Check if model type is supported
        if request.model.type not in [ModelType.API]:
            raise ValueError(f"DeepEval transformer currently only supports API models, got {request.model.type}")
        
        # Check if metrics (datasets) are supported
        unsupported = []
        for dataset in request.datasets:
            if dataset.name.lower() not in self.DATASET_MAPPING:
                unsupported.append(dataset.name)
        
        if unsupported:
            logger.warning(f"The following metrics may not be supported by DeepEval: {unsupported}")
    
    def get_supported_datasets(self) -> List[str]:
        """Get list of metrics supported by DeepEval."""
        return list(self.DATASET_MAPPING.keys())
    
    def get_dataset_mapping(self, dataset_name: str) -> str:
        """Map generic dataset/metric name to DeepEval-specific name."""
        return self.DATASET_MAPPING.get(dataset_name.lower(), dataset_name.lower())