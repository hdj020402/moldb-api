Test script for API functionality.

import os
import tempfile
import shutil
import subprocess
import time
import requests
import threading

def test_lmdb_api():
    """Test LMDB API functionality."""
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_molecules.lmdb")
    
    try:
        # Create a simple test database
        from backend.lmdb import LMDBMoleculeStore
        store = LMDBMoleculeStore(db_path, map_size=1024**3)  # 1GB
        test_inchikey = "UHOVQNZJYSORNB-UHFFFAOYSA-N"
        test_inchi = "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3"
        test_content = "3\n\nC 0 0 0\nH 1 0 0\nH -1 0 0"
        store.put(test_inchikey, test_content)
        store.put(test_inchi, test_content)
        store.close()
        
        # Start the LMDB API service in a separate thread
        env = os.environ.copy()
        env["MOLECULES_LMDB_PATH"] = db_path
        
        # We'll test the API endpoints directly by importing the app
        from service.lmdb_api import app
        import uvicorn
        import asyncio
        
        # Start server in a separate thread
        def run_server():
            uvicorn.run(app, host="127.0.0.1", port=8002, log_level="critical")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Test health check endpoint
        print("Testing health check endpoint...")
        response = requests.get("http://127.0.0.1:8002/")
        assert response.status_code == 200, "Health check failed"
        assert "LMDB Backend is running" in response.json()["message"]
        
        # Test get molecule by InChIKey
        print("Testing get molecule by InChIKey...")
        response = requests.get(f"http://127.0.0.1:8002/molecule/inchikey/{test_inchikey}")
        assert response.status_code == 200, "Get molecule by InChIKey failed"
        data = response.json()
        assert data["identifier"] == test_inchikey
        assert data["content"] == test_content
        
        # Test get molecule by InChI
        print("Testing get molecule by InChI...")
        response = requests.get(f"http://127.0.0.1:8002/molecule/inchi/{test_inchi}")
        assert response.status_code == 200, "Get molecule by InChI failed"
        data = response.json()
        assert data["identifier"] == test_inchi
        assert data["content"] == test_content
        
        print("All LMDB API tests passed!")
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

def test_sqlite_api():
    """Test SQLite API functionality."""
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_molecules.db")
    
    try:
        # Create a simple test database
        from backend.sqlite import SQLiteMoleculeStore
        store = SQLiteMoleculeStore(db_path)
        store.init_db()
        test_inchikey = "UHOVQNZJYSORNB-UHFFFAOYSA-N"
        test_inchi = "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3"
        test_content = "3\n\nC 0 0 0\nH 1 0 0\nH -1 0 0"
        store.put(test_inchikey, test_content, 'inchikey')
        store.put(test_inchi, test_content, 'inchi')
        store.put_inchi_mapping(test_inchi, test_inchikey)
        
        # Start the SQLite API service in a separate thread
        env = os.environ.copy()
        env["MOLECULES_DB_PATH"] = db_path
        
        # We'll test the API endpoints directly by importing the app
        from service.sqlite_api import app
        import uvicorn
        import asyncio
        
        # Start server in a separate thread
        def run_server():
            uvicorn.run(app, host="127.0.0.1", port=8003, log_level="critical")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Test health check endpoint
        print("Testing health check endpoint...")
        response = requests.get("http://127.0.0.1:8003/")
        assert response.status_code == 200, "Health check failed"
        assert "SQLite Backend is running" in response.json()["message"]
        
        # Test get molecule by InChIKey
        print("Testing get molecule by InChIKey...")
        response = requests.get(f"http://127.0.0.1:8003/molecule/inchikey/{test_inchikey}")
        assert response.status_code == 200, "Get molecule by InChIKey failed"
        data = response.json()
        assert data["identifier"] == test_inchikey
        assert data["content"] == test_content
        
        # Test get molecule by InChI
        print("Testing get molecule by InChI...")
        response = requests.get(f"http://127.0.0.1:8003/molecule/inchi/{test_inchi}")
        assert response.status_code == 200, "Get molecule by InChI failed"
        data = response.json()
        assert data["identifier"] == test_inchi
        assert data["content"] == test_content
        
        print("All SQLite API tests passed!")
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_lmdb_api()
    test_sqlite_api()