"""
Shared FastAPI application factory and Pydantic models for moldb API services.

Used by backend-specific modules (lmdb.py, sqlite.py) to avoid code duplication.
"""
import urllib.parse
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    count: int
    conformers: list[dict]


class BatchMoleculeRequest(BaseModel):
    """Request model for batch molecule queries."""
    inchis: list[str] = Field(min_length=1, max_length=10000)


def create_app(
    title: str,
    version: str,
    store_factory: Callable[[], object],
) -> FastAPI:
    """
    Create a fully-configured FastAPI application for a given storage backend.

    Args:
        title: API title shown in docs.
        version: Version string.
        store_factory: Zero-argument callable that returns a store instance.
                       The store must have ``get_conformers``, ``get_many_conformers``,
                       and ``close`` methods.

    Returns:
        A FastAPI application instance with routes registered and lifespan managed.
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
