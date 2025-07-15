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

"""In-memory cache for evaluation dataset manifests with background refresh."""

from __future__ import annotations

import asyncio
from pathlib import Path

from budmicroframe.commons import logging

from budeval.commons.config import app_settings

from .manifest_fetcher import ManifestFetcher
from .manifest_schemas import EvalDataManifest


logger = logging.get_logger(__name__)


class ManifestCache:
    """In-memory cache for evaluation data manifest with background refresh."""

    def __init__(self) -> None:
        self.fetcher = ManifestFetcher()
        self.manifest: EvalDataManifest | None = None
        self.last_synced_version: str | None = None
        self.refresh_task: asyncio.Task | None = None
        self.refresh_interval = app_settings.eval_sync_refresh_seconds
        self.version_file = Path(app_settings.base_dir) / ".eval_manifest_version"

    async def initialize(self) -> None:
        """Initialize the cache by loading the manifest."""
        logger.info("Initializing manifest cache")

        # Load last synced version from file
        await self._load_last_synced_version()

        # Fetch and cache manifest
        await self._refresh_manifest()

        # Start background refresh task if enabled
        if app_settings.eval_sync_enabled:
            self.refresh_task = asyncio.create_task(self._background_refresh())

    async def shutdown(self) -> None:
        """Shutdown the cache and cancel background tasks."""
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("Manifest cache shutdown complete")

    async def get_manifest(self) -> EvalDataManifest:
        """Get the current manifest, initializing if necessary."""
        if self.manifest is None:
            await self.initialize()
        return self.manifest

    async def force_refresh(self) -> None:
        """Force a refresh of the manifest."""
        await self._refresh_manifest()

    async def _refresh_manifest(self) -> None:
        """Refresh the manifest from source."""
        try:
            new_manifest = await self.fetcher.fetch_manifest()
            current_version = new_manifest.version_info.current_version

            # Check if version has changed
            if self.last_synced_version == current_version:
                logger.debug(f"Manifest version unchanged: {current_version}")
                return

            # Update cache
            self.manifest = new_manifest
            self.last_synced_version = current_version

            # Save version to file
            await self._save_last_synced_version()

            logger.info(f"Manifest refreshed successfully. Version: {current_version}")

        except Exception as e:
            logger.error(f"Failed to refresh manifest: {e}")
            if self.manifest is None:
                # If we don't have any manifest yet, re-raise the error
                raise

    async def _background_refresh(self) -> None:
        """Background task to periodically refresh the manifest."""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self._refresh_manifest()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background manifest refresh: {e}")

    async def _load_last_synced_version(self) -> None:
        """Load the last synced version from file."""
        try:
            if self.version_file.exists():
                self.last_synced_version = self.version_file.read_text().strip()
                logger.debug(f"Loaded last synced version: {self.last_synced_version}")
        except Exception as e:
            logger.warning(f"Failed to load last synced version: {e}")

    async def _save_last_synced_version(self) -> None:
        """Save the last synced version to file."""
        try:
            if self.last_synced_version:
                self.version_file.write_text(self.last_synced_version)
                logger.debug(f"Saved last synced version: {self.last_synced_version}")
        except Exception as e:
            logger.warning(f"Failed to save last synced version: {e}")


# Global cache instance
_manifest_cache: ManifestCache | None = None


async def get_manifest_cache() -> ManifestCache:
    """Get the global manifest cache instance."""
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = ManifestCache()
        await _manifest_cache.initialize()
    return _manifest_cache
