# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Code Quality:**
- `ruff check .` - Run linting checks
- `ruff format .` - Auto-format code
- `mypy .` - Type checking

**Testing:**
- `pytest` - Run test suite
- `pytest tests/` - Run specific test directory

**Local Development:**
- `cd deploy && docker-compose -f docker-compose-dev.yaml up` - Start development environment
- `python -m budeval.main` - Run application directly
- API available at `http://localhost:9081`
- `dapr run --run-file ./app.yaml` - Start application with Dapr
- Logs available under `.dapr/logs/`

**Kubernetes Utilities:**
- `python check_volume.py` - Check volume status
- `python test_volume_init.py` - Test volume initialization

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

**API Endpoints:**
- `POST /evals/start` - Submit evaluation jobs
- `GET /evals/status/{job_id}` - Monitor job progress  
- `DELETE /evals/cleanup/{job_id}` - Clean up resources
- `POST /evals/init-volume` - Initialize persistent volumes

**Engine Registry:**
- Engines implement `EngineProtocol` (`budeval/registry/engines/core.py`)
- OpenCompass engine built-in (`budeval/registry/engines/opencompass.py`)
- Docker-based execution with metadata-driven configuration

**Development Environment:**
- Local: Uses `k3s.yaml` for Kubernetes config
- Production: Environment auto-detection via storage config
- Docker Compose setup in `deploy/` directory

## Configuration

- `budeval/commons/config.py` - Application and secrets configuration
- `budeval/commons/storage_config.py` - Environment-aware storage settings  
- `app.yaml` - Dapr application configuration
- Environment variables and kubeconfig handled per-request

## Rules For Claude

- always commit the chages with proper commit message
- make sure to track tasks and its progress in a file to make sure even if session changes , can continue from were we left of