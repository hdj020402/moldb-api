"""
FastAPI service for molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import urllib.parse
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.lmdb import LMDBMoleculeStore
from ..config.config import ApiSettings
from .. import __version__

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


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
) -> FastAPI:
    """Create a fully-configured FastAPI application.

    Args:
        title: API title shown in docs.
        version: Version string.
        store_factory: Zero-argument callable that returns a store instance.
            The store must implement ``get_conformers``, ``get_many_conformers``,
            and ``close``.

    Returns:
        A FastAPI application instance with routes and lifespan.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store_factory()
        yield
        app.state.store.close()

    app = FastAPI(title=title, version=version, lifespan=lifespan)

    @app.get("/")
    async def root():
        """Health check."""
        return {"message": f"{title} is running", "version": version}

    @app.get("/molecule/{inchi:path}", response_model=MoleculeResponse)
    async def get_molecule_by_inchi(request: Request, inchi: str):
        """Retrieve all conformers for a molecule by Fixed-H InChI."""
        decoded_inchi = urllib.parse.unquote(inchi)
        data = request.app.state.store.get_conformers(decoded_inchi)
        if data is None:
            raise HTTPException(status_code=404, detail="Molecule not found")
        return data

    @app.post("/molecules/batch")
    async def get_molecules_batch(request: Request, body: BatchMoleculeRequest):
        """Retrieve multiple molecules' conformers in a single request."""
        decoded_inchis = [urllib.parse.unquote(inchi) for inchi in body.inchis]
        results = request.app.state.store.get_many_conformers(decoded_inchis)
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
):
    """Run the API service.

    Args:
        host: Bind host. None = use config default.
        port: Bind port. None = use config default.
        map_size: LMDB map size in bytes. None = use config default.
        config_path: Path to JSON config file.
    """
    import uvicorn

    s = ApiSettings(config_path=config_path)

    if host is None:
        host = s.host
    if port is None:
        port = s.lmdb_port
    if map_size is None:
        map_size = s.lmdb_map_size

    app = create_app(
        title="moldb-api",
        version=__version__,
        store_factory=lambda: LMDBMoleculeStore(s.lmdb_path, map_size=map_size),
    )

    uvicorn.run(app, host=host, port=port)
