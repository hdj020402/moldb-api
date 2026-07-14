"""moldb — High-performance molecular structure storage and query service."""

import importlib.metadata

__version__ = importlib.metadata.version("moldb")

from moldb.store import LMDBMoleculeStore

__all__ = ["LMDBMoleculeStore", "__version__"]
