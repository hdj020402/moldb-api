"""
Configuration module for moldb-api.
Handles configuration from file, environment variables, and defaults.
"""
import os
import json
from typing import Optional

class Config:
    """Configuration class for moldb-api."""

    def __init__(self, config_file: str = "config.json"):
        """Initialize configuration with optional config file."""
        self.config_file = config_file
        self._config = {}

        # Load from config file if it exists
        self._load_from_file()

        # Override with environment variables
        self._load_from_env()

    def _load_from_file(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_file}: {e}")

    def _load_from_env(self):
        """Load configuration from environment variables."""
        # LMDB database path
        lmdb_path = os.environ.get("MOLECULES_LMDB_PATH")
        if lmdb_path:
            self._config["lmdb_path"] = lmdb_path

        # SQLite database path
        sqlite_path = os.environ.get("MOLECULES_DB_PATH")
        if sqlite_path:
            self._config["sqlite_path"] = sqlite_path

        # API service host
        api_host = os.environ.get("MOLECULES_API_HOST")
        if api_host:
            self._config["api_host"] = api_host

        # LMDB API service port
        lmdb_api_port = os.environ.get("MOLECULES_LMDB_API_PORT")
        if lmdb_api_port:
            self._config["lmdb_api_port"] = int(lmdb_api_port)

        # SQLite API service port
        sqlite_api_port = os.environ.get("MOLECULES_SQLITE_API_PORT")
        if sqlite_api_port:
            self._config["sqlite_api_port"] = int(sqlite_api_port)

        # XYZ path column name
        xyz_path_column = os.environ.get("MOLECULES_XYZ_PATH_COLUMN")
        if xyz_path_column:
            self._config["xyz_path_column"] = xyz_path_column

        # Fixed-H InChI column name
        inchi_column = os.environ.get("MOLECULES_INCHI_COLUMN")
        if inchi_column:
            self._config["inchi_column"] = inchi_column

    def get_lmdb_path(self) -> str:
        """Get LMDB database path."""
        return self._config.get("lmdb_path", "molecules.lmdb")

    def get_sqlite_path(self) -> str:
        """Get SQLite database path."""
        return self._config.get("sqlite_path", "molecules.db")

    def get_api_host(self) -> str:
        """Get API service host."""
        return self._config.get("api_host", "0.0.0.0")

    def get_lmdb_api_port(self) -> int:
        """Get LMDB API service port."""
        return self._config.get("lmdb_api_port", 8000)

    def get_sqlite_api_port(self) -> int:
        """Get SQLite API service port."""
        return self._config.get("sqlite_api_port", 8001)

    def get_xyz_path_column(self) -> str:
        """Get XYZ path column name in CSV."""
        return self._config.get("xyz_path_column", "xyz_path")

    def get_inchi_column(self) -> str:
        """Get Fixed-H InChI column name in CSV."""
        return self._config.get("inchi_column", "fixed_h_inchi")

# Global configuration instance
config = Config()