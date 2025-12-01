"""
LMDB backend implementation for molecular structure data storage.
"""
import os
import lmdb
from typing import Optional, Iterable


class LMDBMoleculeStore:
    """LMDB-based storage for molecular structure data."""

    def __init__(
        self,
        db_path: str,
        map_size: int = 30 * 1024**3,  # 30GB
        sync: bool = True,
        writemap: bool = False,
    ):
        """
        Initialize LMDB storage.

        Args:
            db_path: Path to the LMDB database file
            map_size: Maximum size of the database (default: 30GB)
            sync: If False, use MDB_NOSYNC for faster writes (risk of data loss on crash)
            writemap: If True, use MDB_WRITEMAP (faster on some systems)
        """
        self.db_path = db_path
        self.map_size = map_size

        self.env = lmdb.open(
            self.db_path,
            map_size=self.map_size,
            subdir=False,
            lock=True,
            sync=sync,
            metasync=sync,
            mode=0o644,
            writemap=writemap,
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

    def get_many_by_inchi(self, inchis: list[str]) -> list[tuple[str, Optional[str]]]:
        """
        Retrieve multiple molecule data by InChI in a single transaction.
        
        Args:
            inchis: List of InChI identifiers
            
        Returns:
            List of (inchi, content) tuples, where content is None if not found
        """
        results = []
        with self.env.begin() as txn:
            for inchi in inchis:
                data = txn.get(inchi.encode())
                content = data.decode() if data else None
                results.append((inchi, content))
        return results

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

    def put_many(self, items: Iterable[tuple[str, str]]) -> int:
        """
        Efficiently store many molecules in a single transaction.

        Args:
            items: Iterable of (inchi, content) pairs

        Returns:
            Number of successfully written entries
        """
        count = 0
        with self.env.begin(write=True) as txn:
            for inchi, content in items:
                txn.put(inchi.encode("utf-8"), content.encode("utf-8"))
                count += 1
        return count

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