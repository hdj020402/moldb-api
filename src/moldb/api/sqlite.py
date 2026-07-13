"""
FastAPI service for SQLite-based molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
from ..core.sqlite import SQLiteMoleculeStore
import uvicorn
from ..config.config import ApiSettings
import urllib.parse

settings = ApiSettings()

# Create the FastAPI app
app = FastAPI(
    title="moldb-api - SQLite Backend",
    description="A high-performance service for storing and querying molecular structure data using SQLite backend.",
    version="2.0.0"
)

# Get database path from configuration
DB_PATH = settings.sqlite_path

# Global store instance
STORE = SQLiteMoleculeStore(DB_PATH)
STORE.init_db()


class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    count: int
    conformers: list[dict[str, Any]]


class BatchMoleculeRequest(BaseModel):
    """Request model for batch molecule queries."""
    inchis: list[str]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "moldb-api - SQLite Backend is running", "version": "2.0.0"}


@app.get("/molecule/{inchi:path}", response_model=MoleculeResponse)
async def get_molecule_by_inchi(inchi: str):
    """
    Retrieve all conformers for a molecule by InChI.

    Args:
        inchi: Fixed-H InChI identifier (URL encoded)

    Returns:
        Molecule data with all conformers

    Raises:
        HTTPException: If molecule not found
    """
    # URL decode the InChI parameter
    decoded_inchi = urllib.parse.unquote(inchi)
    data = STORE.get_conformers(decoded_inchi)
    if data is None:
        raise HTTPException(status_code=404, detail="Molecule not found")
    return data


@app.post("/molecules/batch")
async def get_molecules_batch(request: BatchMoleculeRequest):
    """
    Retrieve multiple molecules' conformers by InChI in a single request.

    Args:
        request: Batch request containing a list of Fixed-H InChI identifiers

    Returns:
        Dictionary mapping InChI to molecule data (with count and conformers),
        with None for not found molecules
    """
    response = {}

    try:
        # URL decode all InChI identifiers
        decoded_inchis = [urllib.parse.unquote(inchi) for inchi in request.inchis]

        # Get all results from the store
        results = STORE.get_many_conformers(decoded_inchis)

        # Format the response as a dictionary
        for inchi, data in results:
            response[inchi] = data  # Include even if data is None

    except Exception as e:
        print(f"Error in get_molecules_batch: {e}")
        return {}

    return response


def run_sqlite_api():
    """Run the SQLite API service."""
    uvicorn.run(
        "moldb.api.sqlite:app",
        host=settings.host,
        port=settings.sqlite_port,
        reload=False
    )


if __name__ == "__main__":
    run_sqlite_api()
