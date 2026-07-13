"""
Configuration module for moldb-api.

Loads settings from config/config.json. Falls back to hardcoded defaults.
Split into ApiSettings and BuilderSettings so each module only depends
on the settings it actually needs.
"""
import os
import json


class ApiSettings:
    """API service settings (host, port, DB paths)."""

    def __init__(self, config_file: str = "config/config.json"):
        self._data: dict = self._load_file(config_file)

    @staticmethod
    def _load_file(path: str) -> dict:
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

    def __init__(self, config_file: str = "config/config.json"):
        self._data: dict = self._load_file(config_file)

    @staticmethod
    def _load_file(path: str) -> dict:
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            mapping = json.load(f).get("builder", {}).get("mapping", {})
        return {
            "xyz_path_column": mapping.get("xyz_path_column", "xyz_path"),
            "inchi_column": mapping.get("inchi_column", "fixed_h_inchi"),
        }

    @property
    def xyz_path_column(self) -> str:
        return self._data.get("xyz_path_column", "xyz_path")

    @property
    def inchi_column(self) -> str:
        return self._data.get("inchi_column", "fixed_h_inchi")
