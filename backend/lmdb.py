"""
LMDB backend implementation for molecular structure data storage.
"""
import os
import lmdb
from typing import Optional


class LMDBMoleculeStore:
    """LMDB-based storage for molecular structure data."""
    
    def __init__(self, db_path: str, map_size: int = 30 * 1024**3):  # 30GB
        """
        Initialize LMDB storage.
        
        Args:
            db_path: Path to the LMDB database file
            map_size: Maximum size of the database (default: 30GB)
        """
        self.db_path = db_path
        self.map_size = map_size
        self.env = lmdb.open(
            self.db_path,
            map_size=self.map_size,
            max_dbs=0,
            subdir=False,
            lock=True,
            sync=True,
            metasync=True,
            mode=0o644,
            writemap=False,
            meminit=False,
        )

    def get_by_inchi(self, inchi: str) -> Optional[str]:
        """
        Retrieve molecule data by InChI.
        
        Args:
            inchi: InChI identifier
            
        Returns:
            Molecule data as string, or None if not found
        """
        with self.env.begin() as txn:
            data = txn.get(inchi.encode())
            return data.decode() if data else None

    def put(self, inchi: str, content: str) -> bool:
        """
        Store molecule data.
        
        Args:
            inchi: InChI identifier
            content: Molecule data
            
        Returns:
            True if successful, False otherwise
        """
        with self.env.begin(write=True) as txn:
            return txn.put(inchi.encode(), content.encode())

    def delete(self, inchi: str) -> bool:
        """
        Delete molecule data.
        
        Args:
            inchi: InChI identifier
            
        Returns:
            True if successful, False otherwise
        """
        with self.env.begin(write=True) as txn:
            return txn.delete(inchi.encode())

    def close(self):
        """Close the database connection."""
        self.env.close()