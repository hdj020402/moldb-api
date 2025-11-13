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
    
    def get_lmdb_path(self) -> str:
        """Get LMDB database path."""
        return self._config.get("lmdb_path", "molecules.lmdb")
    
    def get_sqlite_path(self) -> str:
        """Get SQLite database path."""
        return self._config.get("sqlite_path", "molecules.db")

# Global configuration instance
config = Config()