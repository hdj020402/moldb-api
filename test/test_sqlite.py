"""
Test script for SQLite backend functionality.
"""
import os
import tempfile
import shutil
from backend.sqlite import SQLiteMoleculeStore

def test_sqlite_backend():
    """Test SQLite backend functionality."""
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_molecules.db")
    
    try:
        # Initialize store
        store = SQLiteMoleculeStore(db_path)
        store.init_db()
        
        # Test data
        test_inchi = "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3"
        test_content = "3\n\nC 0 0 0\nH 1 0 0\nH -1 0 0"
        
        # Test put operation
        print("Testing put operation...")
        success = store.put(test_inchi, test_content)
        assert success, "Failed to put molecule data"
        
        # Test get_by_inchi operation
        print("Testing get_by_inchi operation...")
        content = store.get_by_inchi(test_inchi)
        assert content == test_content, "Retrieved content doesn't match"
        
        # Test delete operation
        print("Testing delete operation...")
        success = store.delete(test_inchi)
        assert success, "Failed to delete molecule data"
        
        # Verify deletion
        content = store.get_by_inchi(test_inchi)
        assert content is None, "Molecule data should be deleted"
        
        print("All SQLite backend tests passed!")
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_sqlite_backend()