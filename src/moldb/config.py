"""
Configuration module for moldb-api.

Loads settings from a JSON config file. Falls back to hardcoded defaults.
Split into ApiSettings and BuilderSettings so each module only depends
on the settings it actually needs.
"""
import json
import os

_VALID_ON_CONFLICT = {"overwrite", "skip", "merge"}


class ApiSettings:
    """API service settings (host, port, DB path, map size)."""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._data: dict = self._load_file()

    def _load_file(self) -> dict:
        if not os.path.exists(self.config_path):
            raw = {}
        else:
            with open(self.config_path) as f:
                raw = json.load(f).get("api", {})

        port = int(raw.get("lmdb", {}).get("port", 8000))
        if not 1 <= port <= 65535:
            raise ValueError(f"lmdb_port must be 1-65535, got {port}")

        map_size_gb = raw.get("lmdb", {}).get("map_size_gb", 30)
        map_size = map_size_gb * 1024 ** 3
        if map_size < 1024 ** 2:
            raise ValueError(f"lmdb_map_size must be at least 1MB, got {map_size}")

        return {
            "host": raw.get("host", "0.0.0.0"),
            "lmdb_path": raw.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_port": port,
            "lmdb_map_size": map_size,
        }

    @property
    def host(self) -> str:
        return self._data["host"]

    @property
    def lmdb_path(self) -> str:
        return self._data["lmdb_path"]

    @property
    def lmdb_port(self) -> int:
        return self._data["lmdb_port"]

    @property
    def lmdb_map_size(self) -> int:
        return self._data["lmdb_map_size"]


class BuilderSettings:
    """Builder settings (column name defaults for CSV mapping files)."""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._data: dict = self._load_file()

    def _load_file(self) -> dict:
        if not os.path.exists(self.config_path):
            raw = {}
        else:
            with open(self.config_path) as f:
                raw = json.load(f).get("builder", {})

        batch_size = int(raw.get("batch_size", 1000))
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")

        on_conflict = raw.get("on_conflict", "overwrite")
        if on_conflict not in _VALID_ON_CONFLICT:
            raise ValueError(
                f"on_conflict must be one of {_VALID_ON_CONFLICT}, got {on_conflict!r}"
            )

        map_size_gb = raw.get("lmdb", {}).get("map_size_gb", 30)
        map_size = map_size_gb * 1024 ** 3
        if map_size < 1024 ** 2:
            raise ValueError(f"lmdb_map_size must be at least 1MB, got {map_size}")

        mapping = raw.get("mapping", {})
        return {
            "lmdb_path": raw.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_map_size": map_size,
            "batch_size": batch_size,
            "on_conflict": on_conflict,
            "mapping_file": mapping.get("file"),
            "xyz_path_column": mapping.get("xyz_path_column", "xyz_path"),
            "inchi_column": mapping.get("inchi_column", "fixed_h_inchi"),
        }

    @property
    def lmdb_path(self) -> str:
        return self._data["lmdb_path"]

    @property
    def lmdb_map_size(self) -> int:
        return self._data["lmdb_map_size"]

    @property
    def batch_size(self) -> int:
        return self._data["batch_size"]

    @property
    def on_conflict(self) -> str:
        return self._data["on_conflict"]

    @property
    def mapping_file(self) -> str | None:
        return self._data.get("mapping_file")

    @property
    def xyz_path_column(self) -> str:
        return self._data["xyz_path_column"]

    @property
    def inchi_column(self) -> str:
        return self._data["inchi_column"]
