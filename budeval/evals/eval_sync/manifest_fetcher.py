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

"""Fetcher for evaluation dataset manifests from local or remote sources."""

from __future__ import annotations

import json
from pathlib import Path

import aiofiles
import aiohttp
from budmicroframe.commons import logging

from budeval.commons.config import app_settings

from .manifest_schemas import EvalDataManifest


logger = logging.get_logger(__name__)


class ManifestFetcher:
    """Fetches evaluation data manifest from local file or remote URL."""

    def __init__(self) -> None:
        self.local_mode = app_settings.eval_sync_local_mode
        self.manifest_url = app_settings.eval_manifest_url
        self.local_path = Path(app_settings.eval_manifest_local_path)

    async def fetch_manifest(self) -> EvalDataManifest:
        """Fetch manifest from configured source.
        
        Returns:
            EvalDataManifest: Parsed manifest data
            
        Raises:
            FileNotFoundError: If local file doesn't exist
            aiohttp.ClientError: If remote fetch fails
            json.JSONDecodeError: If manifest is invalid JSON
            ValueError: If manifest doesn't match schema
        """
        if self.local_mode:
            return await self._fetch_local_manifest()
        else:
            return await self._fetch_remote_manifest()

    async def _fetch_local_manifest(self) -> EvalDataManifest:
        """Fetch manifest from local file."""
        logger.info(f"Fetching manifest from local file: {self.local_path}")

        if not self.local_path.exists():
            raise FileNotFoundError(f"Local manifest file not found: {self.local_path}")

        async with aiofiles.open(self.local_path, "r", encoding="utf-8") as f:
            content = await f.read()

        try:
            manifest_data = json.loads(content)
            return EvalDataManifest.model_validate(manifest_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in manifest file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse manifest: {e}")
            raise ValueError(f"Invalid manifest format: {e}")

    async def _fetch_remote_manifest(self) -> EvalDataManifest:
        """Fetch manifest from remote URL."""
        logger.info(f"Fetching manifest from remote URL: {self.manifest_url}")

        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout for large files
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.manifest_url) as response:
                response.raise_for_status()
                content = await response.text()

        try:
            manifest_data = json.loads(content)
            return EvalDataManifest.model_validate(manifest_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in remote manifest: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse remote manifest: {e}")
            raise ValueError(f"Invalid manifest format: {e}")
