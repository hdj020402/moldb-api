"""
FastAPI service for SQLite-based molecular structure data storage.
"""
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
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

class MoleculeRequest(BaseModel):
    """Request model for storing molecule data."""
    inchi: str
    content: str

class MoleculeResponse(BaseModel):
    """Response model for molecule data."""
    inchi: str
    content: str

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

@app.post("/molecule", response_model=dict)
async def add_molecule(req: MoleculeRequest):
    """
    Add or update molecule data.
    
    Args:
        req: Molecule data request
        
    Returns:
        Success status
        
    Raises:
        HTTPException: If failed to store molecule
    """
    STORE.put(req.inchi, req.content)
    return {"status": "success", "message": "Molecule data stored successfully"}

@app.delete("/molecule/{inchi:path}", response_model=dict)
async def delete_molecule(inchi: str):
    """
    Delete molecule data.
    
    Args:
        inchi: InChI identifier (URL encoded)
        
    Returns:
        Deletion status
        
    Raises:
        HTTPException: If molecule not found or delete failed
    """
    # URL decode the InChI parameter
    decoded_inchi = urllib.parse.unquote(inchi)
    success = STORE.delete(decoded_inchi)
    if not success:
        raise HTTPException(status_code=404, detail="Molecule not found or delete failed")
    return {"status": "deleted", "message": "Molecule data deleted successfully"}

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