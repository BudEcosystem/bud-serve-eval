# OpenCompass CLI Update Summary

## Changes Made

### 1. Updated OpenCompass Transformer to Use CLI + Environment Variables

**File**: `budeval/core/transformers/opencompass_transformer.py`

**Key Changes**:
- Switched from generating 3 config files to a hybrid approach
- Uses environment variables for API credentials (`OPENAI_API_KEY`, `OPENAI_API_BASE`)
- Generates minimal inline config that reads from environment variables
- Loads dataset mappings from `eval_manifest.json`
- Supports custom model names and base URLs

### 2. Fixed Dataset Transformation Issue

**File**: `budeval/evals/workflows.py`

**Issue**: Datasets from the request were not being converted to `GenericDatasetConfig` objects

**Fix**: Added proper dataset transformation:
```python
datasets=[
    GenericDatasetConfig(
        name=dataset_name,
        category=DatasetCategory.CUSTOM,
        version="1.0.0",
        split="test",
    )
    for dataset_name in (evaluate_model_request_json.datasets or [])
],
```

### 3. Testing Tools Created

**Dynamic Test Script**: `test_dynamic_eval.sh`
- Generates unique eval request IDs
- Checks both API and Kubernetes resources
- Provides colored output for better readability
- Shows pod logs and job details
- Supports custom datasets and API URLs

## Current Status

The code changes are complete, but the service needs to be restarted to pick up the changes. The current running instance still has the old code where datasets are not properly transformed.

## How the New Implementation Works

1. **API Request** comes in with datasets like `["maritimebench"]`

2. **Transformer** converts dataset names using mappings from `eval_manifest.json`:
   - `maritimebench` → `MaritimeBench_gen`

3. **Command Generation** creates a minimal bash script that:
   - Creates a model config file that reads API credentials from environment
   - Runs OpenCompass with CLI arguments: `--datasets MaritimeBench_gen`

4. **Environment Variables** are set in the Kubernetes job:
   - `OPENAI_API_KEY`
   - `OPENAI_API_BASE`

## Benefits of New Approach

1. **Simpler Configuration**: Only one minimal config file instead of three
2. **Dynamic API Support**: Any OpenAI-compatible API can be used
3. **Maintainable Dataset Mapping**: Uses `eval_manifest.json` instead of hardcoded mappings
4. **Environment-based Security**: API keys are not stored in config files

## Next Steps

1. Restart the service to pick up code changes
2. Run `./test_dynamic_eval.sh` to verify the implementation
3. Monitor that datasets are properly passed to OpenCompass

## Example Usage

```bash
# Basic test
./test_dynamic_eval.sh

# Test with custom dataset
DATASET=gsm8k ./test_dynamic_eval.sh

# Test with custom API URL
API_URL=http://custom-host:8099 ./test_dynamic_eval.sh
```