"""
SQLite backend implementation for molecular structure data storage.

Storage scheme:
    Key: {inchi}::meta    → {"count": N}
    Key: {inchi}::conf_0  → {"xyz": "...", ...}
    ...
    Key: {inchi}::conf_{N-1}  → {"xyz": "...", ...}

Each conformer value is a JSON object. The only reserved key is "xyz".
All other keys (energy, source, comment, etc.) are free-form and optional.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import sqlite3
import json
import threading
from typing import Optional, Iterable, Literal, Any, Union

ConflictMode = Literal["overwrite", "skip", "merge"]
ConformerData = dict[str, Any]  # always has "xyz" key

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

    def _conf_prefix(self, inchi: str) -> str:
        """Return the LIKE prefix for conformer keys of a given InChI."""
        return self._make_conf_key(inchi, 0)[:-6]

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

    @staticmethod
    def _serialize_conf(conf: ConformerData) -> str:
        """Serialize a conformer for storage."""
        return json.dumps(conf)

    @staticmethod
    def _deserialize_conf(content: str) -> ConformerData:
        """Deserialize a conformer from storage."""
        return json.loads(content)

    def exists(self, inchi: str) -> bool:
        """Check if a molecule entry exists."""
        cur = self.conn.execute(
            "SELECT 1 FROM molecules WHERE key = ?",
            (self._make_meta_key(inchi),)
        )
        return cur.fetchone() is not None

    def get_conformers(self, inchi: str) -> Optional[dict]:
        """
        Retrieve all conformers for a molecule by InChI.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            Dictionary with 'inchi', 'count', and 'conformers' list,
            or None if not found
        """
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

        cur = self.conn.execute(
            "SELECT key, content FROM molecules WHERE key LIKE ? ORDER BY key",
            (self._conf_prefix(inchi) + "%",)
        )

        conformers = [None] * count
        for row in cur.fetchall():
            key = row[0]
            content = row[1]
            try:
                index_str = key.split(CONF_PREFIX)[-1]
                index = int(index_str)
                if 0 <= index < count:
                    conformers[index] = self._deserialize_conf(content)
            except (ValueError, IndexError):
                continue

        return {
            "inchi": inchi,
            "count": count,
            "conformers": conformers,
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

        meta_keys = [self._make_meta_key(inchi) for inchi in inchis]
        placeholders = ','.join('?' * len(meta_keys))
        query = f"SELECT key, content FROM molecules WHERE key IN ({placeholders})"

        cur = self.conn.execute(query, meta_keys)
        meta_rows = cur.fetchall()

        meta_dict = {}
        for row in meta_rows:
            key = row[0]
            content = row[1]
            inchi = key[:-len(META_SUFFIX)]
            meta_dict[inchi] = json.loads(content)

        for inchi in inchis:
            if inchi not in meta_dict:
                results.append((inchi, None))
                continue

            count = meta_dict[inchi]["count"]

            cur = self.conn.execute(
                "SELECT key, content FROM molecules WHERE key LIKE ? ORDER BY key",
                (self._conf_prefix(inchi) + "%",)
            )

            conformers = [None] * count
            for row in cur.fetchall():
                key = row[0]
                content = row[1]
                try:
                    index_str = key.split(CONF_PREFIX)[-1]
                    index = int(index_str)
                    if 0 <= index < count:
                        conformers[index] = self._deserialize_conf(content)
                except (ValueError, IndexError):
                    continue

            results.append((inchi, {
                "inchi": inchi,
                "count": count,
                "conformers": conformers,
            }))

        return results

    def put_conformers(
        self,
        inchi: str,
        conformers: list[ConformerData],
        on_conflict: ConflictMode = "overwrite",
    ) -> dict:
        """
        Store all conformers for a molecule.

        Args:
            inchi: Fixed-H InChI identifier.
            conformers: List of conformer dicts. Each must have an "xyz" key
                        plus any optional metadata keys (e.g. energy, source).
            on_conflict: How to handle existing entries:
                - "overwrite": Replace existing data (default).
                - "skip": Do nothing if entry already exists.
                - "merge": Append new conformers to existing ones.

        Returns:
            dict with keys:
                - action: "written" | "overwritten" | "skipped" | "merged"
                - count: number of conformers now stored
        """
        meta_key = self._make_meta_key(inchi)
        cur = self.conn.execute(
            "SELECT content FROM molecules WHERE key = ?", (meta_key,)
        )
        existing = cur.fetchone()

        if existing is not None:
            old_meta = json.loads(existing[0])
            old_count = old_meta["count"]

            if on_conflict == "skip":
                return {"action": "skipped", "count": old_count}

            if on_conflict == "merge":
                for i, conf in enumerate(conformers):
                    self.conn.execute(
                        "INSERT INTO molecules (key, content) VALUES (?, ?)",
                        (self._make_conf_key(inchi, old_count + i),
                         self._serialize_conf(conf))
                    )
                new_count = old_count + len(conformers)
                self.conn.execute(
                    "UPDATE molecules SET content = ? WHERE key = ?",
                    (json.dumps({"count": new_count}), meta_key)
                )
                self.conn.commit()
                return {"action": "merged", "count": new_count}

            if on_conflict == "overwrite":
                self._delete_inchi(inchi)

        # Write new entries (first-write and overwrite paths)
        meta = {"count": len(conformers)}
        self.conn.execute(
            "INSERT INTO molecules (key, content) VALUES (?, ?)",
            (meta_key, json.dumps(meta))
        )
        for i, conf in enumerate(conformers):
            self.conn.execute(
                "INSERT INTO molecules (key, content) VALUES (?, ?)",
                (self._make_conf_key(inchi, i), self._serialize_conf(conf))
            )
        self.conn.commit()

        if existing is None:
            action = "written"
        else:
            action = "overwritten"

        return {"action": action, "count": len(conformers)}

    def put_many_conformers(
        self,
        items: Iterable[tuple[str, list[ConformerData]]],
        on_conflict: ConflictMode = "overwrite",
    ) -> dict:
        """
        Efficiently store many molecules' conformers in a single transaction.

        Args:
            items: Iterable of (inchi, conformers_list) pairs.
                   Each conformer can be a bare XYZ string or a dict with metadata.
            on_conflict: How to handle existing entries:
                - "overwrite": Replace existing data (default).
                - "skip": Do nothing if entry already exists.
                - "merge": Append new conformers to existing ones.

        Returns:
            dict with keys: written, overwritten, skipped, merged
        """
        stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}

        for inchi, conformers in items:
            meta_key = self._make_meta_key(inchi)
            cur = self.conn.execute(
                "SELECT content FROM molecules WHERE key = ?", (meta_key,)
            )
            existing = cur.fetchone()

            if existing is not None:
                old_meta_data = existing[0]
                old_meta = json.loads(old_meta_data)
                old_count = old_meta["count"]

                if on_conflict == "skip":
                    stats["skipped"] += 1
                    continue

                if on_conflict == "merge":
                    for i, conf in enumerate(conformers):
                        self.conn.execute(
                            "INSERT INTO molecules (key, content) VALUES (?, ?)",
                            (self._make_conf_key(inchi, old_count + i),
                             self._serialize_conf(conf))
                        )
                    new_count = old_count + len(conformers)
                    self.conn.execute(
                        "UPDATE molecules SET content = ? WHERE key = ?",
                        (json.dumps({"count": new_count}), meta_key)
                    )
                    stats["merged"] += 1
                    continue

                if on_conflict == "overwrite":
                    self._delete_inchi(inchi)
                    stats["overwritten"] += 1
            else:
                stats["written"] += 1

            # Write meta and conformers (first-write and overwrite paths)
            meta = {"count": len(conformers)}
            self.conn.execute(
                "INSERT INTO molecules (key, content) VALUES (?, ?)",
                (meta_key, json.dumps(meta))
            )
            for i, conf in enumerate(conformers):
                self.conn.execute(
                    "INSERT INTO molecules (key, content) VALUES (?, ?)",
                    (self._make_conf_key(inchi, i), self._serialize_conf(conf))
                )

        self.conn.commit()
        return stats

    def _delete_inchi(self, inchi: str):
        """Delete all DB rows for an InChI (internal, no commit)."""
        self.conn.execute(
            "DELETE FROM molecules WHERE key = ? OR key LIKE ?",
            (self._make_meta_key(inchi), self._conf_prefix(inchi) + "%")
        )

    def delete(self, inchi: str) -> bool:
        """
        Delete a molecule and all its conformers.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            True if successful, False if not found
        """
        meta_key = self._make_meta_key(inchi)
        cur = self.conn.execute(
            "SELECT content FROM molecules WHERE key=?",
            (meta_key,)
        )
        if cur.fetchone() is None:
            return False

        self._delete_inchi(inchi)
        self.conn.commit()
        return True

