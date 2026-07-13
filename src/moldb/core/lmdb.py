"""
LMDB backend implementation for molecular structure data storage.

Storage scheme:
    Key: {inchi}::meta    → {"count": N}
    Key: {inchi}::conf_0  → xyz_string_0
    ...
    Key: {inchi}::conf_{N-1}  → xyz_string_{N-1}

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import json
import lmdb
from typing import Optional, Iterable, Literal

ConflictMode = Literal["overwrite", "skip", "merge"]

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

    def exists(self, inchi: str) -> bool:
        """Check if a molecule entry exists."""
        with self.env.begin() as txn:
            return txn.get(self._make_meta_key(inchi)) is not None

    def get_conformers(self, inchi: str) -> Optional[dict]:
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
                    conformers.append(conf_data.decode("utf-8"))

            return {
                "inchi": inchi,
                "count": count,
                "conformers": conformers,
            }

    def get_many_conformers(self, inchis: list[str]) -> list[tuple[str, Optional[dict]]]:
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
                        conformers.append(conf_data.decode("utf-8"))

                results.append((inchi, {
                    "inchi": inchi,
                    "count": count,
                    "conformers": conformers,
                }))

        return results

    def put_conformers(
        self,
        inchi: str,
        conformers: list[str],
        on_conflict: ConflictMode = "overwrite",
    ) -> dict:
        """
        Store all conformers for a molecule.

        Args:
            inchi: Fixed-H InChI identifier.
            conformers: List of XYZ strings, one per conformer.
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
                        txn.put(self._make_conf_key(inchi, old_count + i), conf.encode("utf-8"))
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
                txn.put(self._make_conf_key(inchi, i), conf.encode("utf-8"))

            if existing is None:
                action = "written"
            else:
                action = "overwritten"

            return {"action": action, "count": new_count}

    def put_many_conformers(
        self,
        items: Iterable[tuple[str, list[str]]],
        on_conflict: ConflictMode = "overwrite",
    ) -> dict:
        """
        Efficiently store many molecules' conformers in a single transaction.

        Args:
            items: Iterable of (inchi, conformers_list) pairs.
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
                            txn.put(self._make_conf_key(inchi, old_count + i), conf.encode("utf-8"))
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
                    txn.put(self._make_conf_key(inchi, i), conf.encode("utf-8"))

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

    # --- Legacy API compatibility methods ---

    def get_by_inchi(self, inchi: str) -> Optional[dict]:
        """Retrieve molecule data by InChI (legacy compatible)."""
        return self.get_conformers(inchi)

    def get_many_by_inchi(self, inchis: list[str]) -> list[tuple[str, Optional[dict]]]:
        """Retrieve multiple molecule data by InChI (legacy compatible)."""
        return self.get_many_conformers(inchis)

    def put(self, inchi: str, content: str) -> bool:
        """
        Store molecule data (legacy compatible - treats content as single conformer).

        Always overwrites on conflict.
        """
        self.put_conformers(inchi, [content], on_conflict="overwrite")
        return True

    def put_many(self, items: Iterable[tuple[str, str]]) -> int:
        """
        Store many molecules (legacy compatible - treats each content as single conformer).

        Always overwrites on conflict.
        """
        converted = ((inchi, [content]) for inchi, content in items)
        result = self.put_many_conformers(converted, on_conflict="overwrite")
        return result["written"] + result["overwritten"]

    def close(self):
        """Close the database connection."""
        self.env.close()
