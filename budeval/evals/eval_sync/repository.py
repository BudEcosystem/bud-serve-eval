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

"""Repository interface for evaluation dataset metadata access."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .manifest_schemas import Dataset, TraitDefinition


class EvalDatasetRepository(ABC):
    """Abstract repository interface for evaluation dataset metadata."""
    
    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get a dataset by ID."""
        pass
    
    @abstractmethod
    async def list_datasets(self, traits: list[str] | None = None, source: str | None = None) -> list[Dataset]:
        """List all datasets, optionally filtered by traits or source."""
        pass
    
    @abstractmethod
    async def get_trait(self, trait_name: str) -> TraitDefinition | None:
        """Get a trait definition by name."""
        pass
    
    @abstractmethod
    async def list_traits(self) -> list[TraitDefinition]:
        """List all trait definitions."""
        pass
    
    @abstractmethod
    async def get_datasets_by_trait(self, trait_name: str) -> list[Dataset]:
        """Get all datasets that evaluate a specific trait."""
        pass
    
    @abstractmethod
    async def search_datasets(self, query: str) -> list[Dataset]:
        """Search datasets by name or description."""
        pass
    
    @abstractmethod
    async def get_dataset_sources(self) -> list[str]:
        """Get all available dataset sources."""
        pass
    
    @abstractmethod
    async def get_datasets_by_source(self, source: str) -> list[Dataset]:
        """Get all datasets from a specific source."""
        pass


class InMemoryManifestRepository(EvalDatasetRepository):
    """In-memory implementation of the repository using manifest cache."""
    
    def __init__(self) -> None:
        from .manifest_cache import get_manifest_cache
        self._get_cache = get_manifest_cache
    
    async def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get a dataset by ID."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        for collection in manifest.datasets.values():
            for dataset in collection.datasets:
                if dataset.id == dataset_id:
                    return dataset
        return None
    
    async def list_datasets(self, traits: list[str] | None = None, source: str | None = None) -> list[Dataset]:
        """List all datasets, optionally filtered by traits or source."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        datasets = []
        
        # Filter by source if specified
        if source:
            if source in manifest.datasets:
                datasets.extend(manifest.datasets[source].datasets)
        else:
            # Get all datasets from all sources
            for collection in manifest.datasets.values():
                datasets.extend(collection.datasets)
        
        # Filter by traits if specified
        if traits:
            filtered_datasets = []
            for dataset in datasets:
                if any(trait in dataset.traits for trait in traits):
                    filtered_datasets.append(dataset)
            return filtered_datasets
        
        return datasets
    
    async def get_trait(self, trait_name: str) -> TraitDefinition | None:
        """Get a trait definition by name."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        for trait in manifest.traits.definitions:
            if trait.name == trait_name:
                return trait
        return None
    
    async def list_traits(self) -> list[TraitDefinition]:
        """List all trait definitions."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        return manifest.traits.definitions
    
    async def get_datasets_by_trait(self, trait_name: str) -> list[Dataset]:
        """Get all datasets that evaluate a specific trait."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        datasets = []
        for collection in manifest.datasets.values():
            for dataset in collection.datasets:
                if trait_name in dataset.traits:
                    datasets.append(dataset)
        return datasets
    
    async def search_datasets(self, query: str) -> list[Dataset]:
        """Search datasets by name or description."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        query_lower = query.lower()
        datasets = []
        
        for collection in manifest.datasets.values():
            for dataset in collection.datasets:
                if (query_lower in dataset.name.lower() or 
                    query_lower in dataset.description.lower()):
                    datasets.append(dataset)
        
        return datasets
    
    async def get_dataset_sources(self) -> list[str]:
        """Get all available dataset sources."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        return list(manifest.datasets.keys())
    
    async def get_datasets_by_source(self, source: str) -> list[Dataset]:
        """Get all datasets from a specific source."""
        cache = await self._get_cache()
        manifest = await cache.get_manifest()
        
        if source in manifest.datasets:
            return manifest.datasets[source].datasets
        return []


# Global repository instance
_repository: EvalDatasetRepository | None = None


def get_eval_dataset_repository() -> EvalDatasetRepository:
    """Get the global repository instance."""
    global _repository
    if _repository is None:
        _repository = InMemoryManifestRepository()
    return _repository 