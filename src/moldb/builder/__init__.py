"""
moldb database builder module.

Provides stream-based builders for embedding in preprocessing pipelines,
as well as file-based CLI entry points for disk-based workflows.

Stream builders (programmatic):
    from moldb.builder import build_stream

Mapping-file:
    from moldb.builder import iter_mapping, build_from_mapping
"""
from moldb.builder.lmdb import (
    build_stream,
    build_from_mapping,
    iter_mapping,
    run_build,
)

__all__ = [
    "build_stream",
    "build_from_mapping",
    "iter_mapping",
    "run_build",
]
