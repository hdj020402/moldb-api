"""
FastAPI service for LMDB-based molecular structure data storage.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
from .common import create_app
from ..core.lmdb import LMDBMoleculeStore
from ..config.config import ApiSettings
from .. import __version__

settings = ApiSettings()

app = create_app(
    title="moldb-api - LMDB Backend",
    version=__version__,
    store_factory=lambda: LMDBMoleculeStore(settings.lmdb_path),
)


def run_lmdb_api(args: list[str] | None = None):
    """Run the LMDB API service."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Run LMDB API service"
    )
    parser.add_argument("--host", default=settings.host, help="Bind host")
    parser.add_argument("--port", type=int, default=settings.lmdb_port, help="Bind port")
    parsed = parser.parse_args(args)

    uvicorn.run(
        "moldb.api.lmdb:app",
        host=parsed.host,
        port=parsed.port,
    )
