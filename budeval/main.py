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
from contextlib import asynccontextmanager
from typing import AsyncIterator

from budmicroframe.commons import logging
from budmicroframe.main import configure_app, schedule_secrets_and_config_sync
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from fastapi import FastAPI

from .commons.config import app_settings, secrets_settings
from .commons.exceptions import SeederException
from .evals.routes import evals_routes


# from .seeders import seeders


logger = logging.get_logger(__name__)


# Start Event
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the lifespan of the FastAPI application, including scheduling periodic syncs of configurations and secrets.

    This context manager starts a background task that periodically syncs configurations and secrets from
    their respective stores if they are configured. The sync intervals are randomized between 90% and 100%
    of the maximum sync interval specified in the application settings. The task is canceled upon exiting the
    context.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Yields control back to the context where the lifespan management is performed.
    """
    task = asyncio.create_task(schedule_secrets_and_config_sync())

    try:
        from .evals.volume_init import VolumeInitializer

        logger.info("Starting background initialization on startup")

        volume_init = VolumeInitializer()

        logger.info("Creating background task for volume initialization")
        volume_task = asyncio.create_task(volume_init.ensure_eval_datasets_volume())

        logger.info("Background initialization tasks started successfully")

        logger.info("Prepared dataset successfully.")
    except SeederException as e:
        logger.error("Failed to prepare dataset. Error: %s", e.message)
    except Exception as e:
        logger.error(f"Failed to prepare dataset. Error: {e}")

    yield

    try:
        task.cancel()
    except asyncio.CancelledError:
        logger.exception("Failed to cleanup config & store sync.")

    DaprWorkflow().shutdown_workflow_runtime()


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)

# @app.on_event("startup")  # TODO: change -> https://github.com/BudEcosystem/bud-connect/blob/main/budconnect/main.py
# async def startup_event():
#     """Initialize volumes and preload engines on startup in the background."""
#     try:
#         from .evals.volume_init import VolumeInitializer
#         # from .evals.engine_preloader import EnginePreloader

#         logger.info("Starting background initialization on startup")

#         # Initialize volume initializer and engine preloader
#         volume_init = VolumeInitializer()
#         # engine_preloader = EnginePreloader()

#         # Create background tasks for both volume initialization and engine preloading
#         logger.info("Creating background task for volume initialization")
#         volume_task = asyncio.create_task(volume_init.ensure_eval_datasets_volume())

#         logger.info("Creating background task for engine preloading")
#         # engine_task = asyncio.create_task(engine_preloader.preload_all_engines())

#         logger.info("Background initialization tasks started successfully")

#     except Exception as e:
#         logger.error(f"Failed to start background initialization: {e}", exc_info=True)


app.include_router(evals_routes)
