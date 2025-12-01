"""
SQLite backend implementation for molecular structure data storage.
"""
import sqlite3
from typing import Optional
import threading


class SQLiteMoleculeStore:
    """SQLite-based storage for molecular structure data."""
    
    def __init__(self, db_path: str):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.local = threading.local()

    @property
    def conn(self):
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.execute("PRAGMA journal_mode=WAL;")
            self.local.conn.execute("PRAGMA synchronous=NORMAL;")
        return self.local.conn

    def get_many_by_inchi(self, inchis: list[str]) -> list[tuple[str, Optional[str]]]:
        """
        Retrieve multiple molecule data by InChI.
        
        Args:
            inchis: List of InChI identifiers
            
        Returns:
            List of (inchi, content) tuples, where content is None if not found
        """
        if not inchis:
            return []
            
        # Create placeholders for the SQL query
        placeholders = ','.join('?' * len(inchis))
        query = f"SELECT inchi, content FROM molecules WHERE inchi IN ({placeholders})"
        
        # Execute query
        cur = self.conn.execute(query, inchis)
        results = cur.fetchall()
        
        # Create a dictionary for quick lookup
        result_dict = {row[0]: row[1] for row in results}
        
        # Return results in the same order as input
        return [(inchi, result_dict.get(inchi)) for inchi in inchis]

    def init_db(self):
        """Initialize the database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS molecules (
                inchi TEXT PRIMARY KEY,
                content TEXT NOT NULL
            )
        """)
        
        # Create indexes for better query performance
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inchi ON molecules(inchi)
        """)
        
        self.conn.commit()

    def get_by_inchi(self, inchi: str) -> Optional[str]:
        """
        Retrieve molecule data by InChI.
        
        Args:
            inchi: InChI identifier
            
        Returns:
            Molecule data as string, or None if not found
        """
        cur = self.conn.execute(
            "SELECT content FROM molecules WHERE inchi=?", 
            (inchi,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def put(self, inchi: str, content: str) -> bool:
        """
        Store molecule data.
        
        Args:
            inchi: InChI identifier
            content: Molecule data
            
        Returns:
            True if successful
        """
        self.conn.execute(
            "INSERT OR REPLACE INTO molecules (inchi, content) VALUES (?, ?)",
            (inchi, content)
        )
        self.conn.commit()
        return True

    def put_many(self, items):
        """
        Store multiple molecule data entries in a single transaction.
        
        Args:
            items: Iterable of (inchi, content) pairs
            
        Returns:
            Number of successfully written entries
        """
        count = 0
        try:
            for inchi, content in items:
                self.conn.execute(
                    "INSERT OR REPLACE INTO molecules (inchi, content) VALUES (?, ?)",
                    (inchi, content)
                )
                count += 1
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        return count

    def delete(self, inchi: str) -> bool:
        """
        Delete molecule data.
        
        Args:
            inchi: InChI identifier
            
        Returns:
            True if successful, False otherwise
        """
        cur = self.conn.execute(
            "DELETE FROM molecules WHERE inchi=?", 
            (inchi,)
        )
        self.conn.commit()
        return cur.rowcount > 0