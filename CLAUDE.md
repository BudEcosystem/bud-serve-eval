# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Code Quality:**
- `ruff check .` - Run linting checks (with auto-fix: `ruff check --fix .`)
- `ruff format .` - Auto-format code
- Note: mypy is not installed; ruff handles most linting and formatting

**Testing:**
- `pytest` - Run test suite (requires installation from requirements-test.txt)
- `pytest tests/` - Run specific test directory

**Local Development:**
- `dapr run --run-file ./app.yaml` - Start application with Dapr (recommended)
- Logs available under `.dapr/logs/`

**Kubernetes Utilities:**
- `python tests/check_volume.py` - Check volume status
- `python tests/test_volume_init.py` - Test volume initialization
- `scripts/cleanup_old_volume.sh` - Clean up old Kubernetes volumes
- `scripts/dataset-status` and `scripts/engine-status` - Check dataset and engine status

## Architecture Overview

BudEval is a **microservice evaluation platform** that orchestrates AI model evaluations on Kubernetes clusters. It uses a distributed architecture with Ansible automation and persistent volume management.

**Core Components:**
- `budeval/main.py` - FastAPI application entry point with Dapr integration
- `budeval/evals/` - Core evaluation functionality (routes, services, workflows)
- `budeval/registry/` - Pluggable engine system and orchestration
- `budeval/commons/` - Shared configuration, logging, and utilities

**Key Technologies:**
- **FastAPI + Pydantic** for REST API and data validation
- **Kubernetes** for job execution and resource management
- **Ansible** for infrastructure automation (playbooks in `budeval/ansible/`)
- **Dapr** for microservice communication
- **budmicroframe** for microservice foundations

**Volume Management:**
- Environment-aware storage configuration (`budeval/commons/storage_config.py`)
- Shared `eval-datasets-pvc` for evaluation datasets
- Job-specific volumes for data and output
- Automatic provisioning and cleanup via Ansible playbooks

**Workflow Orchestration:**
- Dapr workflows handle async evaluation execution (`budeval/evals/workflows.py`)
- Activities: config creation, job deployment, progress monitoring
- Kubernetes Jobs with persistent volume mounting for dataset access
- Automatic ConfigMap generation for OpenCompass configurations

**API Endpoints:**
- `POST /evals/start` - Submit evaluation jobs
- `GET /evals/status/{job_id}` - Monitor job progress  
- `DELETE /evals/cleanup/{job_id}` - Clean up resources
- `POST /evals/init-volume` - Initialize persistent volumes
- `POST /evals/preload-engines` - Preload engine Docker images
- ConfigMap management endpoints for OpenCompass configurations

**Engine Registry:**
- Engines implement `EngineProtocol` (`budeval/registry/engines/core.py`)
- OpenCompass engine built-in (`budeval/registry/engines/opencompass.py`)
- Engine preloading system pulls Docker images across cluster nodes
- Dynamic configuration generation for model API endpoints

**Development Environment:**
- Local: Uses `k3s.yaml` for Kubernetes config or in-cluster config
- Environment auto-detection via `StorageConfig.get_environment()`
- Storage classes and access modes configured per environment
- Docker Compose setup in `deploy/` directory

## Configuration

- `budeval/commons/config.py` - Application and secrets configuration (includes dataset URLs)
- `budeval/commons/storage_config.py` - Environment-aware storage settings  
- `app.yaml` - Dapr application configuration (port 8099, components in `.dapr/`)
- Environment variables and kubeconfig handled per-request
- Dataset download URLs configurable via `AppConfig.opencompass_dataset_url`

## Key Integration Points

**Ansible Orchestration** (`budeval/registry/orchestrator/ansible_orchestrator.py`):
- All Kubernetes operations go through Ansible playbooks
- Playbooks in `budeval/ansible/playbooks/` handle job lifecycle
- Dynamic kubeconfig and extravar injection per operation

**ConfigMap Management** (`budeval/evals/configmap_manager.py`):
- Generates OpenCompass Python configs from API parameters
- Creates Kubernetes ConfigMaps with model/dataset configurations
- Handles kubeconfig-based authentication for remote clusters

**Volume Initialization** (`budeval/evals/volume_init.py`):
- Ensures shared dataset PVC exists before job execution  
- Downloads and extracts OpenCompass datasets on first use
- Verifies dataset initialization with marker files

## Code Structure Guidelines

- Follow microservice patterns from `docs/microservice_guidelines.md`
- Use absolute imports for inter-module dependencies
- Configuration through environment variables and Pydantic models
- All Kubernetes operations must use Ansible for consistency
- Engine registry pattern for pluggable evaluation backends