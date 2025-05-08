"""Core runner registry functionality."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, Optional, Protocol, Type, runtime_checkable

from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


# ───────────────────────── Protocol ─────────────────────────

@runtime_checkable
class RunnerProtocol(Protocol):
    """Every runner must know how to submit & manage a job."""

    @abstractmethod
    def submit_job(
        self,
        engine_meta: "EngineMetadata",  # type: ignore[reportUndefinedVariable] # noqa: F821
        engine_args: Dict[str, Any],
    ) -> str:
        """Launch a job and return a **run-id** (opaque to the caller)."""

    @abstractmethod
    def get_job_status(self, run_id: str) -> str:
        """Return one of: PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED."""

    @abstractmethod
    def stop_job(self, run_id: str) -> None:
        """Attempt to cancel/kill a running job."""

    @abstractmethod
    def get_job_logs(self, run_id: str, follow: bool = False) -> str:
        """Return logs (streamed if *follow*)."""


# ───────────────────────── Metadata ─────────────────────────

@dataclass
class RunnerMetadata:
    name: str
    version: str
    description: str
    author: str
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None


# ───────────────────────── Registry ─────────────────────────

class RunnerRegistry:
    """Global registry for runners (Kubernetes, OpenShift, etc.)."""

    _runners: Dict[str, Type[RunnerProtocol]] = {}
    _metadata: Dict[str, RunnerMetadata] = {}

    # Decorator
    @classmethod
    def register(
        cls, metadata: RunnerMetadata
    ) -> Callable[[Type[RunnerProtocol]], Type[RunnerProtocol]]:
        """Register a runner class together with its metadata."""

        def decorator(runner_cls: Type[RunnerProtocol]) -> Type[RunnerProtocol]:
            if not issubclass(runner_cls, RunnerProtocol):
                raise TypeError(f"{runner_cls.__name__} does not implement RunnerProtocol")

            name = metadata.name.lower()
            if name in cls._runners:
                logger.warning("Runner %s already registered – overwriting.", name)

            cls._runners[name] = runner_cls
            cls._metadata[name] = metadata
            logger.info("Registered runner: %s (v%s)", name, metadata.version)
            return runner_cls

        return decorator

    # Lookup helpers
    @classmethod
    @lru_cache(maxsize=32)
    def get_runner(cls, name: str) -> Type[RunnerProtocol]:
        """Get a runner class by name, raising KeyError if not found."""
        name = name.lower()
        if name not in cls._runners:
            raise KeyError(f"Runner {name} not found")
        return cls._runners[name]

    @classmethod
    def get_metadata(cls, name: str) -> RunnerMetadata:
        """Get metadata for a runner by name, raising KeyError if not found."""
        name = name.lower()
        if name not in cls._metadata:
            raise KeyError(f"Metadata for runner {name} not found")
        return cls._metadata[name]

    @classmethod
    def list_runners(cls) -> Dict[str, RunnerMetadata]:
        """Return a dictionary of all registered runners and their metadata."""
        return cls._metadata.copy()

    @classmethod
    def get_runners_by_tag(cls, tag: str) -> Dict[str, RunnerMetadata]:
        """Return a dictionary of runners that have the specified tag."""
        return {n: m for n, m in cls._metadata.items() if tag in m.tags}

    @classmethod
    def get_runners_by_capability(cls, cap: str) -> Dict[str, RunnerMetadata]:
        """Return a dictionary of runners that have the specified capability."""
        return {n: m for n, m in cls._metadata.items() if cap in m.capabilities}
