"""
FastAPI service for SQLite-based molecular structure data storage.
"""
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from ..core.sqlite import SQLiteMoleculeStore
import uvicorn
import os
from ..config.config import config
import urllib.parse

# Create the FastAPI app
app = FastAPI(
    title="moldb-api - SQLite Backend",
    description="A high-performance service for storing and querying molecular structure data using SQLite backend.",
    version="1.0.0"
)

# Get database path from configuration
DB_PATH = config.get_sqlite_path()

# Global store instance
# In production, you might want to use dependency injection or lifespan events
STORE = SQLiteMoleculeStore(DB_PATH)
STORE.init_db()

class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    content: str

class BatchMoleculeRequest(BaseModel):
    """Request model for batch molecule queries."""
    inchis: list[str]

class BatchMoleculeResponse(BaseModel):
    """Response model for batch molecule queries."""
    results: list[MoleculeResponse]

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "moldb-api - SQLite Backend is running"}

@app.get("/molecule/{inchi:path}", response_model=MoleculeResponse)
async def get_molecule_by_inchi(inchi: str):
    """
    Retrieve molecule data by InChI.
    
    Args:
        inchi: InChI identifier (URL encoded)
        
    Returns:
        Molecule data
        
    Raises:
        HTTPException: If molecule not found
    """
    # URL decode the InChI parameter
    decoded_inchi = urllib.parse.unquote(inchi)
    content = STORE.get_by_inchi(decoded_inchi)
    if content is None:
        raise HTTPException(status_code=404, detail="Molecule not found")
    return {"inchi": decoded_inchi, "content": content}

@app.post("/molecules/batch", response_model=dict[str, str])
async def get_molecules_batch(request: BatchMoleculeRequest):
    """
    Retrieve multiple molecule data by InChI in a single request.
    
    Args:
        request: Batch request containing a list of InChI identifiers
        
    Returns:
        Dictionary mapping InChI to content for found molecules
    """
    # URL decode all InChI identifiers
    decoded_inchis = [urllib.parse.unquote(inchi) for inchi in request.inchis]
    
    # Get all results from the store
    results = STORE.get_many_by_inchi(decoded_inchis)
    
    # Format the response as a dictionary, only including found molecules
    response = {}
    for inchi, content in results:
        response[inchi] = content
    
    return response

def run_sqlite_api():
    """Run the SQLite API service."""
    uvicorn.run(
        "moldb.api.sqlite:app", 
        host=config.get_api_host(), 
        port=config.get_sqlite_api_port(),
        reload=False
    )

if __name__ == "__main__":
    run_sqlite_api()