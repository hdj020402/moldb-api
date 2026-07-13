"""
FastAPI service for LMDB-based molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..core.lmdb import LMDBMoleculeStore
import uvicorn
from typing import Any
from ..config.config import config
import urllib.parse

# Create the FastAPI app
app = FastAPI(
    title="moldb-api - LMDB Backend",
    description="A high-performance service for storing and querying molecular structure data using LMDB backend.",
    version="2.0.0"
)

# Get database path from configuration
DB_PATH = config.get_lmdb_path()

# Global store instance
STORE = LMDBMoleculeStore(DB_PATH)


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
    return {"message": "moldb-api - LMDB Backend is running", "version": "2.0.0"}


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


def run_lmdb_api():
    """Run the LMDB API service."""
    uvicorn.run(
        "moldb.api.lmdb:app",
        host=config.get_api_host(),
        port=config.get_lmdb_api_port(),
        reload=False
    )


if __name__ == "__main__":
    run_lmdb_api()
