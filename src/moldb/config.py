"""
Configuration module for moldb-api.

Loads settings from a JSON config file. Falls back to hardcoded defaults.
Split into ApiSettings and BuilderSettings so each module only depends
on the settings it actually needs.
"""
import json
import os

_VALID_ON_CONFLICT = {"overwrite", "skip", "merge"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_json_config(path: str) -> dict:
    """Load a JSON config file, returning {} when the file is missing."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _parse_storage(raw: dict) -> dict:
    """Parse shared ``storage`` section into ``lmdb_path`` and ``lmdb_map_size``."""
    storage = raw.get("storage", {})

    map_size_gb = storage.get("map_size_gb", 30)
    map_size = map_size_gb * 1024 ** 3
    if map_size < 1024 ** 2:
        raise ValueError(f"map_size must be at least 1MB, got {map_size}")

    return {
        "lmdb_path": storage.get("path", "molecules.lmdb"),
        "lmdb_map_size": map_size,
    }


def _parse_logging(section_raw: dict) -> dict:
    """Parse ``logging`` subsection into ``log_level`` and ``log_file``."""
    logging_cfg = section_raw.get("logging", {})

    log_level = logging_cfg.get("level", "INFO").upper()
    if log_level not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}"
        )
    log_file = logging_cfg.get("file", None)

    return {"log_level": log_level, "log_file": log_file}


# ---------------------------------------------------------------------------
# Settings classes
# ---------------------------------------------------------------------------


class ApiSettings:
    """API service settings (host, port, DB path, map size)."""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._data: dict = self._load_file()

    def _load_file(self) -> dict:
        full_raw = _load_json_config(self.config_path)

        raw = full_raw.get("api", {})
        storage_cfg = _parse_storage(full_raw)
        logging_cfg = _parse_logging(raw)

        port = int(raw.get("port", 8000))
        if not 1 <= port <= 65535:
            raise ValueError(f"port must be 1-65535, got {port}")

        return {
            "host": raw.get("host", "0.0.0.0"),
            **storage_cfg,
            "port": port,
            **logging_cfg,
        }

    @property
    def host(self) -> str:
        return self._data["host"]

    @property
    def lmdb_path(self) -> str:
        return self._data["lmdb_path"]

    @property
    def port(self) -> int:
        return self._data["port"]

    @property
    def lmdb_map_size(self) -> int:
        return self._data["lmdb_map_size"]

    @property
    def log_level(self) -> str:
        return self._data["log_level"]

    @property
    def log_file(self) -> str | None:
        return self._data["log_file"]


class BuilderSettings:
    """Builder settings (column name defaults for CSV mapping files)."""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._data: dict = self._load_file()

    def _load_file(self) -> dict:
        full_raw = _load_json_config(self.config_path)

        raw = full_raw.get("builder", {})
        storage_cfg = _parse_storage(full_raw)
        logging_cfg = _parse_logging(raw)

        batch_size = int(raw.get("batch_size", 1000))
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")

        on_conflict = raw.get("on_conflict", "overwrite")
        if on_conflict not in _VALID_ON_CONFLICT:
            raise ValueError(
                f"on_conflict must be one of {_VALID_ON_CONFLICT}, got {on_conflict!r}"
            )

        mapping = raw.get("mapping", {})

        return {
            **storage_cfg,
            "batch_size": batch_size,
            "on_conflict": on_conflict,
            "mapping_file": mapping.get("file"),
            "xyz_path_column": mapping.get("xyz_path_column", "xyz_path"),
            "inchi_column": mapping.get("inchi_column", "fixed_h_inchi"),
            **logging_cfg,
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

    @property
    def log_level(self) -> str:
        return self._data["log_level"]

    @property
    def log_file(self) -> str | None:
        return self._data["log_file"]
