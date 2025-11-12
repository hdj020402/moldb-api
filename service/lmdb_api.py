"""
FastAPI service for LMDB-based molecular structure data storage.
"""
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from backend.lmdb import LMDBMoleculeStore
import uvicorn
import os

# Create the FastAPI app
app = FastAPI(
    title="moldb-api - LMDB Backend",
    description="A high-performance service for storing and querying molecular structure data using LMDB backend.",
    version="1.0.0"
)

# Get database path from environment variable or use default
DB_PATH = os.environ.get("MOLECULES_LMDB_PATH", "molecules.lmdb")

# Global store instance
# In production, you might want to use dependency injection or lifespan events
STORE = LMDBMoleculeStore(DB_PATH)

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
    return {"message": "moldb-api - LMDB Backend is running"}

@app.get("/molecule/{inchi}", response_model=MoleculeResponse)
async def get_molecule_by_inchi(inchi: str):
    """
    Retrieve molecule data by InChI.
    
    Args:
        inchi: InChI identifier
        
    Returns:
        Molecule data
        
    Raises:
        HTTPException: If molecule not found
    """
    content = STORE.get_by_inchi(inchi)
    if content is None:
        raise HTTPException(status_code=404, detail="Molecule not found")
    return {"inchi": inchi, "content": content}

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
    success = STORE.put(req.inchi, req.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store molecule")
    return {"status": "success", "message": "Molecule data stored successfully"}

@app.delete("/molecule/{inchi}", response_model=dict)
async def delete_molecule(inchi: str):
    """
    Delete molecule data.
    
    Args:
        inchi: InChI identifier
        
    Returns:
        Deletion status
        
    Raises:
        HTTPException: If molecule not found or delete failed
    """
    success = STORE.delete(inchi)
    if not success:
        raise HTTPException(status_code=404, detail="Molecule not found or delete failed")
    return {"status": "deleted", "message": "Molecule data deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)