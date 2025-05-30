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

"""The main entry point for the application, initializing the FastAPI app and setting up the application's lifespan management, including configuration and secret syncs."""

import asyncio
from budmicroframe.main import configure_app
from budmicroframe.commons import logging

from .commons.config import app_settings, secrets_settings
from .evals.routes import evals_routes


logger = logging.get_logger(__name__)
app = configure_app(app_settings, secrets_settings)

app.include_router(evals_routes)


@app.on_event("startup")
async def startup_event():
    """Initialize volumes and preload engines on startup in the background."""
    try:
        from .evals.volume_init import VolumeInitializer
        from .evals.engine_preloader import EnginePreloader
        
        logger.info("Starting background initialization on startup")
        
        # Initialize volume initializer and engine preloader
        volume_init = VolumeInitializer()
        engine_preloader = EnginePreloader()
        
        # Create background tasks for both volume initialization and engine preloading
        logger.info("Creating background task for volume initialization")
        volume_task = asyncio.create_task(volume_init.ensure_eval_datasets_volume())
        
        logger.info("Creating background task for engine preloading")
        engine_task = asyncio.create_task(engine_preloader.preload_all_engines())
        
        logger.info("Background initialization tasks started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start background initialization: {e}", exc_info=True)
