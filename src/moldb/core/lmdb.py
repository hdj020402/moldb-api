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
import os
import json
import lmdb
from typing import Optional, Iterable


# Key suffixes for composite keys
META_SUFFIX = "::meta"
CONF_PREFIX = "::conf_"


class LMDBMoleculeStore:
    """LMDB-based storage for molecular structure data with conformer support."""

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

    def _make_meta_key(self, inchi: str) -> bytes:
        """Create meta key for an InChI."""
        return (inchi + META_SUFFIX).encode("utf-8")

    def _make_conf_key(self, inchi: str, index: int) -> bytes:
        """Create conformer key for an InChI and index."""
        return (inchi + CONF_PREFIX + f"{index:06d}").encode("utf-8")

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
            # Get meta info
            meta_key = self._make_meta_key(inchi)
            meta_data = txn.get(meta_key)
            if meta_data is None:
                return None

            meta = json.loads(meta_data.decode("utf-8"))
            count = meta["count"]

            # Get all conformers
            conformers = []
            for i in range(count):
                conf_key = self._make_conf_key(inchi, i)
                conf_data = txn.get(conf_key)
                if conf_data is None:
                    # Should not happen in consistent database
                    conformers.append(None)
                else:
                    conformers.append(conf_data.decode("utf-8"))

            return {
                "inchi": inchi,
                "count": count,
                "conformers": conformers
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
                # Get meta info
                meta_key = self._make_meta_key(inchi)
                meta_data = txn.get(meta_key)

                if meta_data is None:
                    results.append((inchi, None))
                    continue

                meta = json.loads(meta_data.decode("utf-8"))
                count = meta["count"]

                # Get all conformers
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
        with self.env.begin(write=True) as txn:
            # Write meta
            meta = {"count": len(conformers)}
            meta_key = self._make_meta_key(inchi)
            txn.put(meta_key, json.dumps(meta).encode("utf-8"))

            # Write conformers
            for i, conf in enumerate(conformers):
                conf_key = self._make_conf_key(inchi, i)
                txn.put(conf_key, conf.encode("utf-8"))

        return True

    def put_many_conformers(self, items: Iterable[tuple[str, list[str]]]) -> int:
        """
        Efficiently store many molecules' conformers in a single transaction.

        Args:
            items: Iterable of (inchi, conformers_list) pairs

        Returns:
            Number of molecules written
        """
        count = 0
        with self.env.begin(write=True) as txn:
            for inchi, conformers in items:
                # Write meta
                meta = {"count": len(conformers)}
                meta_key = self._make_meta_key(inchi)
                txn.put(meta_key, json.dumps(meta).encode("utf-8"))

                # Write conformers
                for i, conf in enumerate(conformers):
                    conf_key = self._make_conf_key(inchi, i)
                    txn.put(conf_key, conf.encode("utf-8"))

                count += 1

        return count

    def delete(self, inchi: str) -> bool:
        """
        Delete a molecule and all its conformers.

        Args:
            inchi: Fixed-H InChI identifier

        Returns:
            True if successful, False if not found
        """
        with self.env.begin(write=True) as txn:
            # Get meta to know how many conformers to delete
            meta_key = self._make_meta_key(inchi)
            meta_data = txn.get(meta_key)
            if meta_data is None:
                return False

            meta = json.loads(meta_data.decode("utf-8"))
            count = meta["count"]

            # Delete all conformers
            for i in range(count):
                conf_key = self._make_conf_key(inchi, i)
                txn.delete(conf_key)

            # Delete meta
            txn.delete(meta_key)

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

    def close(self):
        """Close the database connection."""
        self.env.close()
