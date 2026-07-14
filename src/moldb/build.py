"""
Build LMDB database from XYZ file iterables or mapping files.

Two usage modes:

1. Stream mode (programmatic) — feed an iterable directly from a pipeline:
   >>> from moldb.build import build_stream
   >>> items = [("InChI=1/...", [{"xyz": "xyz_content_1"}, {"xyz": "xyz_content_2"}]), ...]
   >>> stats = build_stream(items, "molecules.lmdb")
   >>> stats = build_stream(items, "molecules.lmdb", on_conflict="skip")

2. CLI mode (from mapping file) — existing disk-based workflow:
   $ moldb builder --mapping mapping.csv --output molecules.lmdb

CSV format for CLI mode (required):
    xyz_path,fixed_h_inchi
    /path/to/mol1_conf1.xyz,InChI=1/C3H7NO/.../f/h4H2
    /path/to/mol1_conf2.xyz,InChI=1/C3H7NO/.../f/h4H2
    /path/to/mol2_conf1.xyz,InChI=1/C3H7NO/.../f/h5H2

The CSV is grouped by fixed_h_inchi, and all XYZ files for the same InChI
are stored as conformers of that molecule.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option.
"""
import logging
import time
from typing import Iterable

import lmdb
import pandas as pd

from .store import MoleculeStore, ConflictMode, ConformerData, get_db_info
from .config import BuilderSettings
from .logging import setup_logging, BUILDER_LOGGER, STORE_LOGGER

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flush_batch(store, batch, on_conflict, stats):
    """Write a batch to the store and update stats in place.

    Returns (batch_result, batch_time_seconds).
    """
    batch_start = time.time()
    result = store.put_many_conformers(batch, on_conflict=on_conflict)
    for key in ("written", "overwritten", "skipped", "merged"):
        stats[key] += result.get(key, 0)
    batch_time = time.time() - batch_start
    return result, batch_time


def _total_processed(stats):
    """Return the total number of molecules processed across all actions."""
    return stats["written"] + stats["overwritten"] + stats["skipped"] + stats["merged"]


def _log_progress(logger, elapsed, processed, speed, batch_result, batch_time):
    """Log a progress line for a completed batch."""
    parts = [f"W:{batch_result.get('written', 0)}",
             f"O:{batch_result.get('overwritten', 0)}"]
    if batch_result.get("skipped", 0) > 0:
        parts.append(f"S:{batch_result.get('skipped', 0)}")
    if batch_result.get("merged", 0) > 0:
        parts.append(f"M:{batch_result.get('merged', 0)}")
    detail = ",".join(parts)
    logger.info(
        "[%.1fs] Total %d mols, Speed: %.1f mol/s, Batch [%s] in %.2fs",
        elapsed, processed, speed, detail, batch_time,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iter_mapping(
    mapping_file: str,
    xyz_path_column: str = "xyz_path",
    inchi_column: str = "fixed_h_inchi",
):
    """Yield (inchi, conformers) from a CSV mapping file.

    XYZ content read from files is wrapped as {"xyz": content} dicts.

    Args:
        mapping_file: Path to CSV with xyz_path and inchi columns.
        xyz_path_column: Column name for XYZ file paths.
        inchi_column: Column name for Fixed-H InChI.

    Yields:
        (inchi, [conformer_dict]) tuples
    """
    df = pd.read_csv(mapping_file)

    if xyz_path_column not in df.columns or inchi_column not in df.columns:
        raise ValueError(
            f"CSV must have '{xyz_path_column}' and '{inchi_column}' columns"
        )

    for inchi, paths in df.groupby(inchi_column)[xyz_path_column]:
        conformers = []
        for p in paths:
            try:
                with open(p, "r") as f:
                    conformers.append({"xyz": f.read()})
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"XYZ file not found: {p}\n"
                    f"  Referenced by InChI: {inchi}\n"
                    f"  Mapping file: {mapping_file}"
                )
        if conformers:
            yield inchi, conformers


def build_stream(
    items: Iterable[tuple[str, list[ConformerData]]],
    output_path: str,
    map_size: int = 30 * 1024 ** 3,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
) -> dict:
    """Build LMDB database from an iterable of (inchi, conformers) pairs.

    Progress is logged at INFO level. Use ``--log-level WARNING`` to
    suppress progress output.

    Args:
        items: Iterable of (inchi, conformers_list) pairs.
        output_path: Path to output LMDB database file.
        map_size: Maximum database size in bytes (default: 30GB).
        batch_size: Number of molecules per write transaction.
        on_conflict: "overwrite" | "skip" | "merge".

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
    logger = logging.getLogger(BUILDER_LOGGER)
    batch = []
    stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
    total_conformers = 0
    start_time = time.time()

    try:
        with MoleculeStore(output_path, map_size=map_size,
                               sync=False, writemap=True) as store:
            for inchi, conformers in items:
                if not conformers:
                    continue

                batch.append((inchi, conformers))
                total_conformers += len(conformers)

                if len(batch) >= batch_size:
                    result, bt = _flush_batch(store, batch, on_conflict, stats)
                    batch.clear()

                    elapsed = time.time() - start_time
                    tp = _total_processed(stats)
                    _log_progress(logger, elapsed, tp,
                                  tp / elapsed if elapsed > 0 else 0,
                                  result, bt)

            # Final batch
            if batch:
                result, bt = _flush_batch(store, batch, on_conflict, stats)
                elapsed = time.time() - start_time
                tp = _total_processed(stats)
                _log_progress(logger, elapsed, tp,
                              tp / elapsed if elapsed > 0 else 0,
                              result, bt)

    except lmdb.MapFullError:
        raise lmdb.MapFullError(
            f"LMDB map size exhausted. Increase map_size "
            f"(current: {map_size // 1024 ** 3}GB). "
            f"Use --map-size flag or set builder.lmdb.map_size_gb in config."
        )

    total_time = time.time() - start_time
    processed = _total_processed(stats)
    speed = processed / total_time if total_time > 0 else 0
    logger.info(
        "Done. Processed: %d molecules (%s), %d conformers in %.2fs (%.1f mol/s)",
        processed, stats, total_conformers, total_time, speed,
    )

    return {
        "processed": processed,
        "written": stats["written"],
        "overwritten": stats["overwritten"],
        "skipped": stats["skipped"],
        "merged": stats["merged"],
        "conformers": total_conformers,
        "time_seconds": total_time,
    }


def build_from_mapping(
    mapping_file: str,
    output_path: str,
    map_size: int = 30 * 1024 ** 3,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
    xyz_path_column: str = "xyz_path",
    inchi_column: str = "fixed_h_inchi",
) -> dict:
    """Build LMDB database from a CSV mapping file (convenience wrapper)."""
    items = iter_mapping(mapping_file, xyz_path_column, inchi_column)
    return build_stream(items, output_path, map_size, batch_size, on_conflict)


def run_build(
    mapping: str | None = None,
    output: str | None = None,
    map_size: int | None = None,
    batch_size: int | None = None,
    on_conflict: str | None = None,
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
    config_path: str = "config/config.json",
    log_file: str | None = None,
    log_level: str | None = None,
):
    """CLI entry point. All None values fall back to config defaults."""
    cfg = BuilderSettings(config_path=config_path)

    if mapping is None:
        mapping = cfg.mapping_file
    if output is None:
        output = cfg.lmdb_path
    if map_size is None:
        map_size = cfg.lmdb_map_size
    if batch_size is None:
        batch_size = cfg.batch_size
    if on_conflict is None:
        on_conflict = cfg.on_conflict
    if xyz_path_column is None:
        xyz_path_column = cfg.xyz_path_column
    if inchi_column is None:
        inchi_column = cfg.inchi_column

    if not mapping:
        raise ValueError(
            "--mapping is required (or set builder.mapping.file in config.json)"
        )
    if map_size < 1:
        raise ValueError(f"map-size must be positive, got {map_size}")
    if batch_size < 1:
        raise ValueError(f"batch-size must be >= 1, got {batch_size}")

    if log_file is None:
        log_file = cfg.log_file
    if log_level is None:
        log_level = cfg.log_level
    setup_logging(BUILDER_LOGGER, level=log_level, log_file=log_file)
    setup_logging(STORE_LOGGER, level=log_level, log_file=log_file)
    logger = logging.getLogger(BUILDER_LOGGER)
    logger.info("Building database from %s -> %s", mapping, output)
    logger.debug(
        "Builder config: map_size=%d, batch_size=%d, on_conflict=%s",
        map_size, batch_size, on_conflict,
    )

    build_from_mapping(
        mapping, output, map_size, batch_size, on_conflict,
        xyz_path_column, inchi_column,
    )


def run_info(db_path: str, map_size: int | None = None):
    """CLI entry point for ``moldb info`` — print database statistics."""
    if map_size is None:
        map_size = 30 * 1024 ** 3
    if map_size < 1:
        raise ValueError(f"map-size must be positive, got {map_size}")

    info = get_db_info(db_path, map_size=map_size)

    # Human-readable file size
    size_bytes = info["file_size"]
    if size_bytes >= 1024 ** 3:
        size_str = f"{size_bytes / 1024 ** 3:.1f} GB"
    elif size_bytes >= 1024 ** 2:
        size_str = f"{size_bytes / 1024 ** 2:.1f} MB"
    elif size_bytes >= 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes} B"

    print(f"Database:    {db_path}")
    print(f"Molecules:   {info['molecules']:,}")
    print(f"Conformers:  {info['conformers']:,}")
    print(f"File size:   {size_str}")
