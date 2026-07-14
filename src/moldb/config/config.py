"""
Configuration module for moldb-api.

Loads settings from a JSON config file. Falls back to hardcoded defaults.
The config file path is set by the CLI via ``set_config_path()`` before
any settings objects are instantiated.

Split into ApiSettings and BuilderSettings so each module only depends
on the settings it actually needs.
"""
import json
import os


_config_path: str = "config/config.json"


def set_config_path(path: str):
    """Set the config file path (called by CLI before instantiation)."""
    global _config_path
    _config_path = os.path.abspath(path) if not os.path.isabs(path) else path


class ApiSettings:
    """API service settings (host, port, DB paths)."""

    def __init__(self):
        self._data: dict = self._load_file()

    @staticmethod
    def _load_file() -> dict:
        path = _config_path
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            api = json.load(f).get("api", {})
        return {
            "host": api.get("host", "0.0.0.0"),
            "lmdb_path": api.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_port": api.get("lmdb", {}).get("port", 8000),
            "sqlite_path": api.get("sqlite", {}).get("path", "molecules.db"),
            "sqlite_port": api.get("sqlite", {}).get("port", 8001),
        }

    @property
    def host(self) -> str:
        return self._data.get("host", "0.0.0.0")

    @property
    def lmdb_path(self) -> str:
        return self._data.get("lmdb_path", "molecules.lmdb")

    @property
    def lmdb_port(self) -> int:
        return int(self._data.get("lmdb_port", 8000))

    @property
    def sqlite_path(self) -> str:
        return self._data.get("sqlite_path", "molecules.db")

    @property
    def sqlite_port(self) -> int:
        return int(self._data.get("sqlite_port", 8001))


class BuilderSettings:
    """Builder settings (column name defaults for CSV mapping files)."""

    def __init__(self):
        self._data: dict = self._load_file()

    @staticmethod
    def _load_file() -> dict:
        path = _config_path
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            cfg = json.load(f)
            builder = cfg.get("builder", {})
            mapping = builder.get("mapping", {})
        return {
            "lmdb_path": builder.get("lmdb", {}).get("path", "molecules.lmdb"),
            "lmdb_map_size": builder.get("lmdb", {}).get("map_size_gb", 30) * 1024 ** 3,
            "sqlite_path": builder.get("sqlite", {}).get("path", "molecules.db"),
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
        return self._data.get("lmdb_map_size", 30 * 1024 ** 3)

    @property
    def sqlite_path(self) -> str:
        return self._data.get("sqlite_path", "molecules.db")

    @property
    def batch_size(self) -> int:
        return self._data.get("batch_size", 1000)

    @property
    def on_conflict(self) -> str:
        return self._data.get("on_conflict", "overwrite")

    @property
    def mapping_file(self) -> str | None:
        return self._data.get("mapping_file")

    @property
    def xyz_path_column(self) -> str:
        return self._data.get("xyz_path_column", "xyz_path")

    @property
    def inchi_column(self) -> str:
        return self._data.get("inchi_column", "fixed_h_inchi")
