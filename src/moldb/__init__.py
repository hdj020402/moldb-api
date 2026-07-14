"""moldb — High-performance molecular structure storage and query service."""

import importlib.metadata

__version__ = importlib.metadata.version("moldb")

from moldb.store import MoleculeStore, get_db_info

__all__ = ["MoleculeStore", "get_db_info", "__version__"]
