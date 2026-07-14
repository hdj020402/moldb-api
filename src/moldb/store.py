"""
Molecular structure data storage backed by LMDB.

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
import logging
import os
import lmdb
from typing import Iterable, Literal, Any

from .logging import STORE_LOGGER

ConflictMode = Literal["overwrite", "skip", "merge"]
ConformerData = dict[str, Any]  # always has "xyz" key

# Key suffixes for composite keys
META_SUFFIX = "::meta"
CONF_PREFIX = "::conf_"

logger = logging.getLogger(STORE_LOGGER)


class MoleculeStore:
    """Storage for molecular structure data with conformer support."""

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
        if map_size < 1024 ** 2:
            raise ValueError(f"map_size must be at least 1MB, got {map_size}")

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
        logger.debug("Opened store at %s (map_size=%d, sync=%s, writemap=%s)",
                     db_path, map_size, sync, writemap)

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

    def _get_conformers_txn(self, txn, inchi: str) -> dict | None:
        """Retrieve all conformers for a molecule within an existing transaction.

        Single InChI lookup is the primitive; batch lookups reuse this.
        """
        meta_key = self._make_meta_key(inchi)
        meta_data = txn.get(meta_key)
        if meta_data is None:
            return None

        meta = json.loads(meta_data.decode("utf-8"))
        count = meta["count"]

        conformers = []
        for i in range(count):
            conf_data = txn.get(self._make_conf_key(inchi, i))
            if conf_data is not None:
                conformers.append(self._deserialize_conf(conf_data))

        return {
            "inchi": inchi,
            "count": count,
            "conformers": conformers,
        }

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
            return self._get_conformers_txn(txn, inchi)

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
                result = self._get_conformers_txn(txn, inchi)
                results.append((inchi, result))
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
        if not conformers:
            raise ValueError("conformers must not be empty")
        if any("xyz" not in c for c in conformers):
            raise ValueError("every conformer must have an 'xyz' key")

        with self.env.begin(write=True) as txn:
            meta_key = self._make_meta_key(inchi)
            existing = txn.get(meta_key)

            if existing is not None:
                old_meta = json.loads(existing.decode("utf-8"))
                old_count = old_meta["count"]

                if on_conflict == "skip":
                    logger.debug("put_conformers: %s skipped (%d existing conformers)",
                                inchi, old_count)
                    return {"action": "skipped", "count": old_count}
                elif on_conflict == "merge":
                    # Append-only: write new conformers starting at old_count,
                    # leaving existing conformer keys untouched.
                    for i, conf in enumerate(conformers):
                        txn.put(self._make_conf_key(inchi, old_count + i),
                                self._serialize_conf(conf))
                    new_count = old_count + len(conformers)
                    txn.put(meta_key, json.dumps({"count": new_count}).encode("utf-8"))
                    logger.debug("put_conformers: %s merged %d → %d conformers",
                                inchi, len(conformers), new_count)
                    return {"action": "merged", "count": new_count}
                elif on_conflict == "overwrite":
                    # Clean up stale conformer keys (if new count is smaller)
                    if old_count > len(conformers):
                        for i in range(len(conformers), old_count):
                            txn.delete(self._make_conf_key(inchi, i))
                else:
                    raise ValueError(
                        f"invalid on_conflict: {on_conflict!r}"
                    )

            new_count = len(conformers)
            meta = {"count": new_count}
            txn.put(meta_key, json.dumps(meta).encode("utf-8"))

            for i, conf in enumerate(conformers):
                txn.put(self._make_conf_key(inchi, i), self._serialize_conf(conf))

            if existing is None:
                action = "written"
            else:
                action = "overwritten"

            logger.debug("put_conformers: %s %s (%d conformers)",
                        inchi, action, new_count)
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
                   Each conformer must be a dict with an "xyz" key.
            on_conflict: How to handle existing entries:
                - "overwrite": Replace existing data (default).
                - "skip": Do nothing if entry already exists.
                - "merge": Append new conformers to existing ones.

        Returns:
            dict with keys: written, overwritten, skipped, merged
        """
        stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
        item_count = 0

        with self.env.begin(write=True) as txn:
            for inchi, conformers in items:
                if not conformers:
                    raise ValueError("conformers must not be empty")
                if any("xyz" not in c for c in conformers):
                    raise ValueError("every conformer must have an 'xyz' key")

                item_count += 1

                meta_key = self._make_meta_key(inchi)
                existing = txn.get(meta_key)

                if existing is not None:
                    old_meta = json.loads(existing.decode("utf-8"))
                    old_count = old_meta["count"]

                    if on_conflict == "skip":
                        stats["skipped"] += 1
                        continue
                    elif on_conflict == "merge":
                        # Append-only: write new conformers after existing ones
                        for i, conf in enumerate(conformers):
                            txn.put(self._make_conf_key(inchi, old_count + i),
                                    self._serialize_conf(conf))
                        new_count = old_count + len(conformers)
                        txn.put(meta_key, json.dumps({"count": new_count}).encode("utf-8"))
                        stats["merged"] += 1
                        continue
                    elif on_conflict == "overwrite":
                        # Clean up stale conformer keys (if new count is smaller)
                        if old_count > len(conformers):
                            for i in range(len(conformers), old_count):
                                txn.delete(self._make_conf_key(inchi, i))
                        stats["overwritten"] += 1
                    else:
                        raise ValueError(
                            f"invalid on_conflict: {on_conflict!r}"
                        )
                else:
                    stats["written"] += 1

                # Write meta and conformers (overwrite and first-write paths)
                meta = {"count": len(conformers)}
                txn.put(meta_key, json.dumps(meta).encode("utf-8"))
                for i, conf in enumerate(conformers):
                    txn.put(self._make_conf_key(inchi, i), self._serialize_conf(conf))

        logger.debug("put_many_conformers: %d molecules, stats=%s", item_count, stats)
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
                logger.debug("delete: %s not found", inchi)
                return False

            meta = json.loads(meta_data.decode("utf-8"))
            count = meta["count"]

            for i in range(count):
                txn.delete(self._make_conf_key(inchi, i))

            txn.delete(meta_key)

        logger.debug("delete: %s removed (%d conformers)", inchi, count)
        return True

    def close(self):
        """Close the database connection."""
        logger.debug("Closing store at %s", self.db_path)
        self.env.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def get_db_info(db_path: str, map_size: int = 30 * 1024 ** 3) -> dict:
    """Open *db_path* read-only and return molecule / conformer counts.

    Returns a dict with keys ``molecules``, ``conformers``, and ``file_size``.
    """
    env = lmdb.open(
        db_path,
        map_size=map_size,
        subdir=False,
        readonly=True,
        lock=False,
        meminit=False,
    )
    try:
        molecules = 0
        conformers = 0
        with env.begin() as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                key_str = key.decode("utf-8", errors="replace")
                if key_str.endswith(META_SUFFIX):
                    molecules += 1
                    meta = json.loads(value.decode("utf-8"))
                    conformers += meta.get("count", 0)
    finally:
        env.close()

    file_size = os.path.getsize(db_path)

    return {
        "molecules": molecules,
        "conformers": conformers,
        "file_size": file_size,
    }
