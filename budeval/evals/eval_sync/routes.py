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

"""API routes for evaluation dataset metadata."""

from __future__ import annotations

from typing import Any

from budmicroframe.commons import logging
from fastapi import APIRouter, HTTPException, Query

from .manifest_schemas import Dataset, TraitDefinition
from .repository import get_eval_dataset_repository


logger = logging.get_logger(__name__)

router = APIRouter(prefix="/eval-datasets", tags=["eval-datasets"])


@router.get("/datasets", response_model=list[Dataset])
async def list_datasets(
    traits: list[str] | None = Query(None, description="Filter by traits"),
    source: str | None = Query(None, description="Filter by source")
) -> list[Dataset]:
    """List all available evaluation datasets."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.list_datasets(traits=traits, source=source)
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets")


@router.get("/datasets/{dataset_id}", response_model=Dataset)
async def get_dataset(dataset_id: str) -> Dataset:
    """Get a specific dataset by ID."""
    try:
        repo = get_eval_dataset_repository()
        dataset = await repo.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset")


@router.get("/datasets/search", response_model=list[Dataset])
async def search_datasets(
    q: str = Query(..., description="Search query")
) -> list[Dataset]:
    """Search datasets by name or description."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.search_datasets(q)
    except Exception as e:
        logger.error(f"Failed to search datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to search datasets")


@router.get("/traits", response_model=list[TraitDefinition])
async def list_traits() -> list[TraitDefinition]:
    """List all available evaluation traits."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.list_traits()
    except Exception as e:
        logger.error(f"Failed to list traits: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve traits")


@router.get("/traits/{trait_name}", response_model=TraitDefinition)
async def get_trait(trait_name: str) -> TraitDefinition:
    """Get a specific trait by name."""
    try:
        repo = get_eval_dataset_repository()
        trait = await repo.get_trait(trait_name)
        if not trait:
            raise HTTPException(status_code=404, detail="Trait not found")
        return trait
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trait {trait_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trait")


@router.get("/traits/{trait_name}/datasets", response_model=list[Dataset])
async def get_datasets_by_trait(trait_name: str) -> list[Dataset]:
    """Get all datasets that evaluate a specific trait."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_datasets_by_trait(trait_name)
    except Exception as e:
        logger.error(f"Failed to get datasets for trait {trait_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets")


@router.get("/sources", response_model=list[str])
async def get_dataset_sources() -> list[str]:
    """Get all available dataset sources."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_dataset_sources()
    except Exception as e:
        logger.error(f"Failed to get dataset sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sources")


@router.get("/sources/{source}/datasets", response_model=list[Dataset])
async def get_datasets_by_source(source: str) -> list[Dataset]:
    """Get all datasets from a specific source."""
    try:
        repo = get_eval_dataset_repository()
        return await repo.get_datasets_by_source(source)
    except Exception as e:
        logger.error(f"Failed to get datasets for source {source}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets")


@router.post("/refresh")
async def refresh_manifest() -> dict[str, Any]:
    """Force refresh of the evaluation dataset manifest."""
    try:
        from .manifest_cache import get_manifest_cache

        cache = await get_manifest_cache()
        await cache.force_refresh()

        manifest = await cache.get_manifest()
        return {
            "message": "Manifest refreshed successfully",
            "version": manifest.version_info.current_version,
            "last_updated": manifest.last_updated,
            "manifest_version": manifest.manifest_version,
            "total_datasets": sum(collection.count for collection in manifest.datasets.values()),
            "total_traits": manifest.traits.count
        }
    except Exception as e:
        logger.error(f"Failed to refresh manifest: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh manifest")
