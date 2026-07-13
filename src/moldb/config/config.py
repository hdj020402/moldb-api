"""
Configuration module for moldb-api.

Loads defaults from config/config.json, overrides with environment variables.
Split into ApiSettings and BuilderSettings so each module only depends
on the settings it actually needs.
"""
import os
import json


class ApiSettings:
    """API service settings (host, port, DB paths)."""

    def __init__(self, config_file: str = "config/config.json"):
        self._data: dict = {}
        self._load_file(config_file)
        self._load_env()

    def _load_file(self, path: str):
        if not os.path.exists(path):
            return
        with open(path) as f:
            api = json.load(f).get("api", {})
        self._data["host"] = api.get("host", "0.0.0.0")
        self._data["lmdb_path"] = api.get("lmdb", {}).get("path", "molecules.lmdb")
        self._data["lmdb_port"] = api.get("lmdb", {}).get("port", 8000)
        self._data["sqlite_path"] = api.get("sqlite", {}).get("path", "molecules.db")
        self._data["sqlite_port"] = api.get("sqlite", {}).get("port", 8001)

    def _load_env(self):
        mapping = [
            ("MOLECULES_API_HOST", "host"),
            ("MOLECULES_LMDB_PATH", "lmdb_path"),
            ("MOLECULES_LMDB_API_PORT", "lmdb_port"),
            ("MOLECULES_SQLITE_PATH", "sqlite_path"),    # alias: MOLECULES_DB_PATH
            ("MOLECULES_SQLITE_API_PORT", "sqlite_port"),
        ]
        for env_key, field in mapping:
            if env_key in os.environ:
                self._data[field] = os.environ[env_key]

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
        self._data: dict = {}
        self._load_file(config_file)
        self._load_env()

    def _load_file(self, path: str):
        if not os.path.exists(path):
            return
        with open(path) as f:
            mapping = json.load(f).get("builder", {}).get("mapping", {})
        self._data["xyz_path_column"] = mapping.get("xyz_path_column", "xyz_path")
        self._data["inchi_column"] = mapping.get("inchi_column", "fixed_h_inchi")

    def _load_env(self):
        mapping = [
            ("MOLECULES_XYZ_PATH_COLUMN", "xyz_path_column"),
            ("MOLECULES_INCHI_COLUMN", "inchi_column"),
        ]
        for env_key, field in mapping:
            if env_key in os.environ:
                self._data[field] = os.environ[env_key]

    @property
    def xyz_path_column(self) -> str:
        return self._data.get("xyz_path_column", "xyz_path")

    @property
    def inchi_column(self) -> str:
        return self._data.get("inchi_column", "fixed_h_inchi")
