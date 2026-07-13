"""
moldb database builder module.

Provides stream-based builders for embedding in preprocessing pipelines,
as well as file-based CLI entry points for disk-based workflows.

Stream builders (programmatic):
    from moldb.builder.lmdb import build_lmdb_stream
    from moldb.builder.sqlite import build_sqlite_stream

Mapping-file helpers (disk-based):
    from moldb.builder.lmdb import iter_mapping, build_lmdb_from_mapping
    from moldb.builder.sqlite import iter_mapping, build_sqlite_from_mapping
"""
from moldb.builder.lmdb import (
    build_lmdb_stream,
    build_lmdb_from_mapping,
    iter_mapping as iter_mapping_lmdb,
    run_build_lmdb,
)
from moldb.builder.sqlite import (
    build_sqlite_stream,
    build_sqlite_from_mapping,
    iter_mapping as iter_mapping_sqlite,
    run_build_sqlite,
)

__all__ = [
    "build_lmdb_stream",
    "build_lmdb_from_mapping",
    "iter_mapping_lmdb",
    "run_build_lmdb",
    "build_sqlite_stream",
    "build_sqlite_from_mapping",
    "iter_mapping_sqlite",
    "run_build_sqlite",
]
