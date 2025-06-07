"""Config generator for OpenCompass model configurations."""

from typing import Dict, Any
from budeval.commons.logging import logging

logger = logging.getLogger(__name__)


class OpenCompassConfigGenerator:
    """Generates OpenCompass configuration files dynamically."""

    @staticmethod
    def generate_bud_model_config(
        model_name: str,
        api_key: str,
        base_url: str,
        eval_request_id: str,
        **kwargs
    ) -> str:
        """Generate bud-model.py content with actual payload data.
        
        Args:
            model_name: The model name/path
            api_key: API key for authentication
            base_url: Base URL for the API
            eval_request_id: Unique evaluation request ID
            **kwargs: Additional configuration parameters
            
        Returns:
            str: The Python configuration file content
        """
        # Extract additional parameters with defaults
        max_out_len = kwargs.get('max_out_len', 2048)
        max_seq_len = kwargs.get('max_seq_len', 4096)
        batch_size = kwargs.get('batch_size', 8)
        query_per_second = kwargs.get('query_per_second', 1)
        temperature = kwargs.get('temperature', 0.0)
        
        config_content = f'''# OpenCompass model configuration for evaluation request: {eval_request_id}
# Generated automatically - do not edit manually

from opencompass.models import OpenAI

models = [
    dict(
        abbr='{model_name}',
        type=OpenAI,
        path='{model_name}',
        key='{api_key}',
        query_per_second={query_per_second},
        max_out_len={max_out_len},
        max_seq_len={max_seq_len},
        openai_api_base='{base_url}',
        batch_size={batch_size},
        temperature={temperature},
        run_cfg=dict(num_gpus=0),
        retry=3,
    ),
]

# Evaluation metadata
eval_metadata = {{
    'eval_request_id': '{eval_request_id}',
    'model_name': '{model_name}',
    'base_url': '{base_url}',
    'generated_at': '{{}}',
}}
'''
        
        # Add timestamp
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat() + 'Z'
        config_content = config_content.format(timestamp)
        
        logger.info(f"Generated bud-model.py config for model: {model_name}")
        return config_content

    @staticmethod
    def generate_dataset_config(datasets: list[str]) -> str:
        """Generate dataset configuration.
        
        Args:
            datasets: List of dataset names to evaluate
            
        Returns:
            str: The dataset configuration content
        """
        # For now, use a default set of datasets
        # This can be expanded to support custom dataset selection
        dataset_imports = []
        dataset_list = []
        
        # Map common dataset names to their import paths
        dataset_mapping = {
            'mmlu': 'from .datasets.mmlu.mmlu_gen import mmlu_datasets',
            'gsm8k': 'from .datasets.gsm8k.gsm8k_gen import gsm8k_datasets',
            'hellaswag': 'from .datasets.hellaswag.hellaswag_gen import hellaswag_datasets',
            'arc': 'from .datasets.ARC_c.ARC_c_gen import ARC_c_datasets',
            'winogrande': 'from .datasets.winogrande.winogrande_gen import winogrande_datasets',
        }
        
        for dataset in datasets:
            if dataset.lower() in dataset_mapping:
                dataset_imports.append(dataset_mapping[dataset.lower()])
                dataset_list.append(f"{dataset.lower()}_datasets")
        
        # Default to basic datasets if none specified
        if not dataset_imports:
            dataset_imports = [
                'from .datasets.mmlu.mmlu_gen import mmlu_datasets',
                'from .datasets.gsm8k.gsm8k_gen import gsm8k_datasets',
            ]
            dataset_list = ['mmlu_datasets', 'gsm8k_datasets']
        
        config_content = f'''# Dataset configuration
from mmengine.config import read_base

with read_base():
    {chr(10).join(f"    {imp}" for imp in dataset_imports)}

datasets = [*{', *'.join(dataset_list)}]
'''
        
        return config_content 