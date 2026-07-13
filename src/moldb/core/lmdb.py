"""
LMDB backend implementation for molecular structure data storage.

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
import json
import lmdb
from typing import Iterable, Literal, Any

ConflictMode = Literal["overwrite", "skip", "merge"]
ConformerData = dict[str, Any]  # always has "xyz" key

# Key suffixes for composite keys
META_SUFFIX = "::meta"
CONF_PREFIX = "::conf_"


class LMDBMoleculeStore:
    """LMDB-based storage for molecular structure data with conformer support."""

    def __init__(
        self,
        db_path: str,
        map_size: int = 30 * 1024 ** 3,  # 30GB
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

    def _make_meta_key(self, inchi: str) -> bytes:
        """Create meta key for an InChI."""
        return (inchi + META_SUFFIX).encode("utf-8")

    def _make_conf_key(self, inchi: str, index: int) -> bytes:
        """Create conformer key for an InChI and index."""
        return (inchi + CONF_PREFIX + f"{index:06d}").encode("utf-8")

    @staticmethod
    def _serialize_conf(conf: ConformerData) -> bytes:
        """Serialize a conformer for storage."""
        return json.dumps(conf).encode("utf-8")

    @staticmethod
    def _deserialize_conf(raw: bytes) -> ConformerData:
        """Deserialize a conformer from storage."""
        return json.loads(raw.decode("utf-8"))

    def exists(self, inchi: str) -> bool:
        """Check if a molecule entry exists."""
        with self.env.begin() as txn:
            return txn.get(self._make_meta_key(inchi)) is not None

    def get_conformers(self, inchi: str) -> dict | None:
        """
        Retrieve all conformers for a molecule by InChI.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            Dictionary with 'inchi', 'count', and 'conformers' list,
            or None if not found
        """
        with self.env.begin() as txn:
            meta_key = self._make_meta_key(inchi)
            meta_data = txn.get(meta_key)
            if meta_data is None:
                return None

            meta = json.loads(meta_data.decode("utf-8"))
            count = meta["count"]

            conformers = []
            for i in range(count):
                conf_key = self._make_conf_key(inchi, i)
                conf_data = txn.get(conf_key)
                if conf_data is None:
                    conformers.append(None)
                else:
                    conformers.append(self._deserialize_conf(conf_data))

            return {
                "inchi": inchi,
                "count": count,
                "conformers": conformers,
            }

    def get_many_conformers(self, inchis: list[str]) -> list[tuple[str, dict | None]]:
        """
        Retrieve multiple molecules' conformers by InChI in a single transaction.

        Args:
            inchis: List of Fixed-H InChI identifiers

        Returns:
            List of (inchi, conformers_dict) tuples, where conformers_dict is None if not found
        """
        results = []
        with self.env.begin() as txn:
            for inchi in inchis:
                meta_key = self._make_meta_key(inchi)
                meta_data = txn.get(meta_key)

                if meta_data is None:
                    results.append((inchi, None))
                    continue

                meta = json.loads(meta_data.decode("utf-8"))
                count = meta["count"]

                conformers = []
                for i in range(count):
                    conf_key = self._make_conf_key(inchi, i)
                    conf_data = txn.get(conf_key)
                    if conf_data is None:
                        conformers.append(None)
                    else:
                        conformers.append(self._deserialize_conf(conf_data))

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
        with self.env.begin(write=True) as txn:
            meta_key = self._make_meta_key(inchi)
            existing = txn.get(meta_key)

            if existing is not None:
                old_meta = json.loads(existing.decode("utf-8"))
                old_count = old_meta["count"]

                if on_conflict == "skip":
                    return {"action": "skipped", "count": old_count}

                if on_conflict == "merge":
                    # Append-only: write new conformers starting at old_count,
                    # leaving existing conformer keys untouched.
                    for i, conf in enumerate(conformers):
                        txn.put(self._make_conf_key(inchi, old_count + i),
                                self._serialize_conf(conf))
                    new_count = old_count + len(conformers)
                    txn.put(meta_key, json.dumps({"count": new_count}).encode("utf-8"))
                    return {"action": "merged", "count": new_count}

                if on_conflict == "overwrite":
                    # Clean up stale conformer keys (if new count is smaller)
                    if old_count > len(conformers):
                        for i in range(len(conformers), old_count):
                            txn.delete(self._make_conf_key(inchi, i))

            new_count = len(conformers)
            meta = {"count": new_count}
            txn.put(meta_key, json.dumps(meta).encode("utf-8"))

            for i, conf in enumerate(conformers):
                txn.put(self._make_conf_key(inchi, i), self._serialize_conf(conf))

            if existing is None:
                action = "written"
            else:
                action = "overwritten"

            return {"action": action, "count": new_count}

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

        with self.env.begin(write=True) as txn:
            for inchi, conformers in items:
                meta_key = self._make_meta_key(inchi)
                existing = txn.get(meta_key)

                if existing is not None:
                    old_meta = json.loads(existing.decode("utf-8"))
                    old_count = old_meta["count"]

                    if on_conflict == "skip":
                        stats["skipped"] += 1
                        continue

                    if on_conflict == "merge":
                        # Append-only: write new conformers after existing ones
                        for i, conf in enumerate(conformers):
                            txn.put(self._make_conf_key(inchi, old_count + i),
                                    self._serialize_conf(conf))
                        new_count = old_count + len(conformers)
                        txn.put(meta_key, json.dumps({"count": new_count}).encode("utf-8"))
                        stats["merged"] += 1
                        continue

                    if on_conflict == "overwrite":
                        # Clean up stale conformer keys (if new count is smaller)
                        if old_count > len(conformers):
                            for i in range(len(conformers), old_count):
                                txn.delete(self._make_conf_key(inchi, i))
                        stats["overwritten"] += 1
                else:
                    stats["written"] += 1

                # Write meta and conformers (overwrite and first-write paths)
                meta = {"count": len(conformers)}
                txn.put(meta_key, json.dumps(meta).encode("utf-8"))
                for i, conf in enumerate(conformers):
                    txn.put(self._make_conf_key(inchi, i), self._serialize_conf(conf))

        return stats

    def delete(self, inchi: str) -> bool:
        """
        Delete a molecule and all its conformers.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            True if successful, False if not found
        """
        with self.env.begin(write=True) as txn:
            meta_key = self._make_meta_key(inchi)
            meta_data = txn.get(meta_key)
            if meta_data is None:
                return False

            meta = json.loads(meta_data.decode("utf-8"))
            count = meta["count"]

            for i in range(count):
                txn.delete(self._make_conf_key(inchi, i))

            txn.delete(meta_key)

        return True

    def close(self):
        """Close the database connection."""
        self.env.close()
