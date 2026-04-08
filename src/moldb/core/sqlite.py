"""
SQLite backend implementation for molecular structure data storage.

Storage scheme:
    Key: {inchi}::meta    → {"count": N}
    Key: {inchi}::conf_0  → xyz_string_0
    ...
    Key: {inchi}::conf_{N-1}  → xyz_string_{N-1}

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import sqlite3
import json
from typing import Optional, Iterable
import threading


# Key suffixes for composite keys
META_SUFFIX = "::meta"
CONF_PREFIX = "::conf_"


class SQLiteMoleculeStore:
    """SQLite-based storage for molecular structure data with conformer support."""

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

    def _make_meta_key(self, inchi: str) -> str:
        """Create meta key for an InChI."""
        return inchi + META_SUFFIX

    def _make_conf_key(self, inchi: str, index: int) -> str:
        """Create conformer key for an InChI and index."""
        return inchi + CONF_PREFIX + f"{index:06d}"

    def init_db(self):
        """Initialize the database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS molecules (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_key ON molecules(key)
        """)

        self.conn.commit()

    def get_conformers(self, inchi: str) -> Optional[dict]:
        """
        Retrieve all conformers for a molecule by InChI.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            Dictionary with 'inchi', 'count', and 'conformers' list,
            or None if not found
        """
        # Get meta info
        meta_key = self._make_meta_key(inchi)
        cur = self.conn.execute(
            "SELECT content FROM molecules WHERE key=?",
            (meta_key,)
        )
        row = cur.fetchone()
        if row is None:
            return None

        meta = json.loads(row[0])
        count = meta["count"]

        # Get all conformers using LIKE query
        conf_prefix = self._make_conf_key(inchi, 0)[:-6]  # Remove the index part
        cur = self.conn.execute(
            "SELECT key, content FROM molecules WHERE key LIKE ? ORDER BY key",
            (conf_prefix + "%",)
        )

        conformers = [None] * count  # Pre-allocate list
        for row in cur.fetchall():
            key = row[0]
            content = row[1]
            # Extract index from key
            try:
                index_str = key.split(CONF_PREFIX)[-1]
                index = int(index_str)
                if 0 <= index < count:
                    conformers[index] = content
            except (ValueError, IndexError):
                continue

        return {
            "inchi": inchi,
            "count": count,
            "conformers": conformers
        }

    def get_many_conformers(self, inchis: list[str]) -> list[tuple[str, Optional[dict]]]:
        """
        Retrieve multiple molecules' conformers by InChI.

        Args:
            inchis: List of Fixed-H InChI identifiers

        Returns:
            List of (inchi, conformers_dict) tuples, where conformers_dict is None if not found
        """
        if not inchis:
            return []

        results = []

        # Get all meta info first
        meta_keys = [self._make_meta_key(inchi) for inchi in inchis]
        placeholders = ','.join('?' * len(meta_keys))
        query = f"SELECT key, content FROM molecules WHERE key IN ({placeholders})"

        cur = self.conn.execute(query, meta_keys)
        meta_rows = cur.fetchall()

        # Build meta dict
        meta_dict = {}
        for row in meta_rows:
            key = row[0]
            content = row[1]
            # Extract inchi from meta key
            inchi = key[:-len(META_SUFFIX)]
            meta_dict[inchi] = json.loads(content)

        # Now get conformers for each found molecule
        for inchi in inchis:
            if inchi not in meta_dict:
                results.append((inchi, None))
                continue

            count = meta_dict[inchi]["count"]
            conf_prefix = self._make_conf_key(inchi, 0)[:-6]  # Remove the index part

            cur = self.conn.execute(
                "SELECT key, content FROM molecules WHERE key LIKE ? ORDER BY key",
                (conf_prefix + "%",)
            )

            conformers = [None] * count
            for row in cur.fetchall():
                key = row[0]
                content = row[1]
                try:
                    index_str = key.split(CONF_PREFIX)[-1]
                    index = int(index_str)
                    if 0 <= index < count:
                        conformers[index] = content
                except (ValueError, IndexError):
                    continue

            results.append((inchi, {
                "inchi": inchi,
                "count": count,
                "conformers": conformers
            }))

        return results

    def put_conformers(self, inchi: str, conformers: list[str]) -> bool:
        """
        Store all conformers for a molecule.

        Args:
            inchi: Fixed-H InChI identifier
            conformers: List of XYZ strings, one per conformer

        Returns:
            True if successful
        """
        # Delete existing entries for this inchi
        self.delete(inchi)

        # Write meta
        meta = {"count": len(conformers)}
        meta_key = self._make_meta_key(inchi)
        self.conn.execute(
            "INSERT INTO molecules (key, content) VALUES (?, ?)",
            (meta_key, json.dumps(meta))
        )

        # Write conformers
        for i, conf in enumerate(conformers):
            conf_key = self._make_conf_key(inchi, i)
            self.conn.execute(
                "INSERT INTO molecules (key, content) VALUES (?, ?)",
                (conf_key, conf)
            )

        self.conn.commit()
        return True

    def put_many_conformers(self, items: Iterable[tuple[str, list[str]]]) -> int:
        """
        Store many molecules' conformers in a single transaction.

        Args:
            items: Iterable of (inchi, conformers_list) pairs

        Returns:
            Number of molecules written
        """
        count = 0
        items_list = list(items)  # Convert to list for deletion pass

        # Delete existing entries
        for inchi, _ in items_list:
            conf_prefix = self._make_conf_key(inchi, 0)[:-6]
            self.conn.execute(
                "DELETE FROM molecules WHERE key = ? OR key LIKE ?",
                (self._make_meta_key(inchi), conf_prefix + "%")
            )

        # Insert new entries
        for inchi, conformers in items_list:
            # Write meta
            meta = {"count": len(conformers)}
            meta_key = self._make_meta_key(inchi)
            self.conn.execute(
                "INSERT INTO molecules (key, content) VALUES (?, ?)",
                (meta_key, json.dumps(meta))
            )

            # Write conformers
            for i, conf in enumerate(conformers):
                conf_key = self._make_conf_key(inchi, i)
                self.conn.execute(
                    "INSERT INTO molecules (key, content) VALUES (?, ?)",
                    (conf_key, conf)
                )

            count += 1

        self.conn.commit()
        return count

    def delete(self, inchi: str) -> bool:
        """
        Delete a molecule and all its conformers.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            True if successful, False if not found
        """
        # Check if exists
        meta_key = self._make_meta_key(inchi)
        cur = self.conn.execute(
            "SELECT content FROM molecules WHERE key=?",
            (meta_key,)
        )
        row = cur.fetchone()
        if row is None:
            return False

        # Delete all entries with this inchi prefix
        conf_prefix = self._make_conf_key(inchi, 0)[:-6]
        self.conn.execute(
            "DELETE FROM molecules WHERE key = ? OR key LIKE ?",
            (meta_key, conf_prefix + "%")
        )
        self.conn.commit()
        return True

    # Legacy API compatibility methods

    def get_by_inchi(self, inchi: str) -> Optional[dict]:
        """
        Retrieve molecule data by InChI (legacy compatible).

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            Dictionary with molecule data, or None if not found
        """
        return self.get_conformers(inchi)

    def get_many_by_inchi(self, inchis: list[str]) -> list[tuple[str, Optional[dict]]]:
        """
        Retrieve multiple molecule data by InChI (legacy compatible).

        Args:
            inchis: List of Fixed-H InChI identifiers

        Returns:
            List of (inchi, data_dict) tuples
        """
        return self.get_many_conformers(inchis)

    def put(self, inchi: str, content: str) -> bool:
        """
        Store molecule data (legacy compatible - treats content as single conformer).

        Args:
            inchi: Fixed-H InChI identifier
            content: XYZ string

        Returns:
            True if successful
        """
        return self.put_conformers(inchi, [content])

    def put_many(self, items: Iterable[tuple[str, str]]) -> int:
        """
        Store many molecules (legacy compatible - treats each content as single conformer).

        Args:
            items: Iterable of (inchi, content) pairs

        Returns:
            Number of molecules written
        """
        converted = ((inchi, [content]) for inchi, content in items)
        return self.put_many_conformers(converted)
