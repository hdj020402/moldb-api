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
            
        # XYZ directory for LMDB build
        lmdb_xyz_dir = os.environ.get("MOLECULES_LMDB_XYZ_DIR")
        if lmdb_xyz_dir:
            self._config["lmdb_xyz_dir"] = lmdb_xyz_dir
            
        # XYZ directory for SQLite build
        sqlite_xyz_dir = os.environ.get("MOLECULES_SQLITE_XYZ_DIR")
        if sqlite_xyz_dir:
            self._config["sqlite_xyz_dir"] = sqlite_xyz_dir
            
        # InChI mapping file for LMDB build
        lmdb_inchi_mapping = os.environ.get("MOLECULES_LMDB_INCHI_MAPPING")
        if lmdb_inchi_mapping:
            self._config["lmdb_inchi_mapping"] = lmdb_inchi_mapping
            
        # InChI mapping file for SQLite build
        sqlite_inchi_mapping = os.environ.get("MOLECULES_SQLITE_INCHI_MAPPING")
        if sqlite_inchi_mapping:
            self._config["sqlite_inchi_mapping"] = sqlite_inchi_mapping
            
        # InChIKey column name
        inchikey_column = os.environ.get("MOLECULES_INCHIKEY_COLUMN")
        if inchikey_column:
            self._config["inchikey_column"] = inchikey_column
            
        # InChI column name
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
        
    def get_lmdb_xyz_dir(self) -> str:
        """Get XYZ directory for LMDB build."""
        return self._config.get("lmdb_xyz_dir", "./data/xyz_files")
        
    def get_sqlite_xyz_dir(self) -> str:
        """Get XYZ directory for SQLite build."""
        return self._config.get("sqlite_xyz_dir", "./data/xyz_files")
        
    def get_lmdb_inchi_mapping(self) -> str:
        """Get InChI mapping file for LMDB build."""
        return self._config.get("lmdb_inchi_mapping", "inchi_mapping.csv")
        
    def get_sqlite_inchi_mapping(self) -> str:
        """Get InChI mapping file for SQLite build."""
        return self._config.get("sqlite_inchi_mapping", "inchi_mapping.csv")
        
    def get_inchikey_column(self) -> str:
        """Get InChIKey column name."""
        return self._config.get("inchikey_column", "inchikey")
        
    def get_inchi_column(self) -> str:
        """Get InChI column name."""
        return self._config.get("inchi_column", "inchi")

# Global configuration instance
config = Config()