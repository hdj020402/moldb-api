"""
FastAPI service for SQLite-based molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..core.sqlite import SQLiteMoleculeStore
from ..config.config import ApiSettings
import uvicorn
import urllib.parse

settings = ApiSettings()

app = FastAPI(
    title="moldb-api - SQLite Backend",
    description="A high-performance service for storing and querying molecular structure data using SQLite backend.",
    version="2.0.0",
)

store = SQLiteMoleculeStore(settings.sqlite_path)
store.init_db()


class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    count: int
    conformers: list[dict]


class BatchMoleculeRequest(BaseModel):
    """Request model for batch molecule queries."""
    inchis: list[str]


@app.get("/")
async def root():
    """Health check."""
    return {"message": "moldb-api - SQLite Backend is running", "version": "2.0.0"}


@app.get("/molecule/{inchi:path}", response_model=MoleculeResponse)
async def get_molecule_by_inchi(inchi: str):
    """Retrieve all conformers for a molecule by Fixed-H InChI."""
    decoded_inchi = urllib.parse.unquote(inchi)
    data = store.get_conformers(decoded_inchi)
    if data is None:
        raise HTTPException(status_code=404, detail="Molecule not found")
    return data


@app.post("/molecules/batch")
async def get_molecules_batch(request: BatchMoleculeRequest):
    """Retrieve multiple molecules' conformers in a single request."""
    decoded_inchis = [urllib.parse.unquote(inchi) for inchi in request.inchis]
    results = store.get_many_conformers(decoded_inchis)
    return {inchi: data for inchi, data in results}


def run_sqlite_api():
    """Run the SQLite API service."""
    uvicorn.run("moldb.api.sqlite:app", host=settings.host, port=settings.sqlite_port)


if __name__ == "__main__":
    run_sqlite_api()
