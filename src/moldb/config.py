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
            return {}
        with open(self.config_path) as f:
            api = json.load(f).get("api", {})
        return {
            "host": api.get("host", "0.0.0.0"),
            "lmdb_path": api.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_port": api.get("lmdb", {}).get("port", 8000),
            "lmdb_map_size": api.get("lmdb", {}).get("map_size_gb", 30) * 1024 ** 3,
        }

    @property
    def host(self) -> str:
        return self._data.get("host", "0.0.0.0")

    @property
    def lmdb_path(self) -> str:
        return self._data.get("lmdb_path", "molecules.lmdb")

    @property
    def lmdb_port(self) -> int:
        port = int(self._data.get("lmdb_port", 8000))
        if not 1 <= port <= 65535:
            raise ValueError(f"lmdb_port must be 1-65535, got {port}")
        return port

    @property
    def lmdb_map_size(self) -> int:
        size = int(self._data.get("lmdb_map_size", 30 * 1024 ** 3))
        if size < 1024 ** 2:
            raise ValueError(f"lmdb_map_size must be at least 1MB, got {size}")
        return size


class BuilderSettings:
    """Builder settings (column name defaults for CSV mapping files)."""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._data: dict = self._load_file()

    def _load_file(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path) as f:
            cfg = json.load(f)
            builder = cfg.get("builder", {})
            mapping = builder.get("mapping", {})
        return {
            "lmdb_path": builder.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_map_size": builder.get("lmdb", {}).get("map_size_gb", 30) * 1024 ** 3,
            "batch_size": builder.get("batch_size", 1000),
            "on_conflict": builder.get("on_conflict", "overwrite"),
            "mapping_file": mapping.get("file"),
            "xyz_path_column": mapping.get("xyz_path_column", "xyz_path"),
            "inchi_column": mapping.get("inchi_column", "fixed_h_inchi"),
        }

    @property
    def lmdb_path(self) -> str:
        return self._data.get("lmdb_path", "molecules.lmdb")

    @property
    def lmdb_map_size(self) -> int:
        size = int(self._data.get("lmdb_map_size", 30 * 1024 ** 3))
        if size < 1024 ** 2:
            raise ValueError(f"lmdb_map_size must be at least 1MB, got {size}")
        return size

    @property
    def batch_size(self) -> int:
        size = int(self._data.get("batch_size", 1000))
        if size < 1:
            raise ValueError(f"batch_size must be >= 1, got {size}")
        return size

    @property
    def on_conflict(self) -> str:
        mode = self._data.get("on_conflict", "overwrite")
        if mode not in _VALID_ON_CONFLICT:
            raise ValueError(
                f"on_conflict must be one of {_VALID_ON_CONFLICT}, got {mode!r}"
            )
        return mode

    @property
    def mapping_file(self) -> str | None:
        return self._data.get("mapping_file")

    @property
    def xyz_path_column(self) -> str:
        return self._data.get("xyz_path_column", "xyz_path")

    @property
    def inchi_column(self) -> str:
        return self._data.get("inchi_column", "fixed_h_inchi")
