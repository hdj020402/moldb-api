"""
FastAPI service for molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .store import MoleculeStore
from .config import ApiSettings
from .logging import setup_logging, build_uvicorn_log_config, API_LOGGER, STORE_LOGGER
from . import __version__

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class MoleculeRequest(BaseModel):
    """Request model for single-molecule query."""
    inchi: str


class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    count: int
    conformers: list[dict]


class BatchMoleculeRequest(BaseModel):
    """Request model for batch molecule queries."""
    inchis: list[str] = Field(min_length=1, max_length=10000)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(
    title: str,
    version: str,
    store_factory: Callable[[], object],
    db_path: str = "",
) -> FastAPI:
    """Create a fully-configured FastAPI application.

    Args:
        title: API title shown in docs.
        version: Version string.
        store_factory: Zero-argument callable that returns a store instance.
            The store must implement ``get_conformers``, ``get_many_conformers``,
            and ``close``.
        db_path: Path to the LMDB database (shown in health check).

    Returns:
        A FastAPI application instance with routes and lifespan.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger = logging.getLogger(API_LOGGER)
        logger.info("Opening store at %s", db_path)
        app.state.store = store_factory()
        yield
        logger.info("Closing store at %s", db_path)
        app.state.store.close()

    app = FastAPI(title=title, version=version, lifespan=lifespan)

    @app.get("/")
    async def root():
        """Health check."""
        return {
            "message": f"{title} is running",
            "version": version,
            "database": db_path,
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger(API_LOGGER)
        logger.exception(
            "Unhandled error on %s %s: %s",
            request.method, request.url.path, exc,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.post("/molecule")
    async def get_molecule(request: Request, body: MoleculeRequest):
        """Retrieve all conformers for a molecule by Fixed-H InChI."""
        data = request.app.state.store.get_conformers(body.inchi)
        return {body.inchi: data}

    @app.post("/molecules/batch")
    async def get_molecules_batch(request: Request, body: BatchMoleculeRequest):
        """Retrieve multiple molecules' conformers in a single request."""
        results = request.app.state.store.get_many_conformers(body.inchis)
        return {inchi: data for inchi, data in results}

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run_api(
    host: str | None = None,
    port: int | None = None,
    map_size: int | None = None,
    config_path: str = "config/config.json",
    log_file: str | None = None,
    log_level: str | None = None,
):
    """Run the API service.

    Args:
        host: Bind host. None = use config default.
        port: Bind port. None = use config default.
        map_size: LMDB map size in bytes. None = use config default.
        config_path: Path to JSON config file.
        log_file: Log file path. None = use config default.
        log_level: Log level. None = use config default.
    """
    import uvicorn

    s = ApiSettings(config_path=config_path)

    if host is None:
        host = s.host
    if port is None:
        port = s.port
    if map_size is None:
        map_size = s.lmdb_map_size
    if map_size < 1:
        raise ValueError(f"map-size must be positive, got {map_size}")
    if log_file is None:
        log_file = s.log_file
    if log_level is None:
        log_level = s.log_level

    # Configure application logging
    setup_logging(API_LOGGER, level=log_level, log_file=log_file)
    setup_logging(STORE_LOGGER, level=log_level, log_file=log_file)
    logger = logging.getLogger(API_LOGGER)

    # Build uvicorn log config that mirrors app log format
    uvicorn_log_config = build_uvicorn_log_config(
        log_file=log_file, level=log_level,
    )

    app = create_app(
        title="moldb-api",
        version=__version__,
        store_factory=lambda: MoleculeStore(s.lmdb_path, map_size=map_size),
        db_path=s.lmdb_path,
    )

    logger.info("Starting moldb-api on %s:%s (db=%s, map_size=%d)",
                host, port, s.lmdb_path, map_size)
    uvicorn.run(app, host=host, port=port, log_config=uvicorn_log_config)
