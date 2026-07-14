"""
FastAPI service for SQLite-based molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import sqlite3

from .common import create_app
from ..core.sqlite import SQLiteMoleculeStore
from ..config.config import ApiSettings
from .. import __version__

settings = ApiSettings()


def _sqlite_store_factory():
    store = SQLiteMoleculeStore(settings.sqlite_path)
    try:
        store.init_db()
    except sqlite3.OperationalError:
        store.close()
        raise
    return store


app = create_app(
    title="moldb-api - SQLite Backend",
    version=__version__,
    store_factory=_sqlite_store_factory,
)


def run_sqlite_api(args: list[str] | None = None):
    """Run the SQLite API service."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Run SQLite API service"
    )
    parser.add_argument("--host", default=settings.host, help="Bind host")
    parser.add_argument("--port", type=int, default=settings.sqlite_port, help="Bind port")
    parsed = parser.parse_args(args)

    uvicorn.run(
        "moldb.api.sqlite:app",
        host=parsed.host,
        port=parsed.port,
    )
