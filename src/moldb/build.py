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
import time
from typing import Iterable

import lmdb
import pandas as pd

from .store import MoleculeStore, ConflictMode, ConformerData
from .config import BuilderSettings

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


def _print_progress(elapsed, processed, speed, batch_result, batch_time):
    """Print a progress line for a completed batch."""
    parts = [f"W:{batch_result.get('written', 0)}",
             f"O:{batch_result.get('overwritten', 0)}"]
    if batch_result.get("skipped"):
        parts.append(f"S:{batch_result['skipped']}")
    if batch_result.get("merged"):
        parts.append(f"M:{batch_result['merged']}")
    detail = ",".join(parts)
    print(
        f"[{elapsed:.1f}s] Total {processed} mols, "
        f"Speed: {speed:.1f} mol/s, "
        f"Batch [{detail}] in {batch_time:.2f}s"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def iter_mapping(
    mapping_file: str,
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
    config_path: str = "config/config.json",
):
    """Yield (inchi, conformers) from a CSV mapping file.

    XYZ content read from files is wrapped as {"xyz": content} dicts.

    Args:
        mapping_file: Path to CSV with xyz_path and inchi columns.
        xyz_path_column: Column name for XYZ file paths (default from config).
        inchi_column: Column name for Fixed-H InChI (default from config).
        config_path: Path to config file.

    Yields:
        (inchi, [conformer_dict]) tuples
    """
    cfg = BuilderSettings(config_path=config_path)
    if xyz_path_column is None:
        xyz_path_column = cfg.xyz_path_column
    if inchi_column is None:
        inchi_column = cfg.inchi_column

    df = pd.read_csv(mapping_file)

    if xyz_path_column not in df.columns or inchi_column not in df.columns:
        raise ValueError(
            f"CSV must have '{xyz_path_column}' and '{inchi_column}' columns"
        )

    for inchi, paths in df.groupby(inchi_column)[xyz_path_column]:
        conformers = []
        for p in paths:
            with open(p, "r") as f:
                conformers.append({"xyz": f.read()})
        if conformers:
            yield inchi, conformers


def build_stream(
    items: Iterable[tuple[str, list[ConformerData]]],
    output_path: str,
    map_size: int = 30 * 1024 ** 3,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
    verbose: bool = True,
) -> dict:
    """Build LMDB database from an iterable of (inchi, conformers) pairs.

    Args:
        items: Iterable of (inchi, conformers_list) pairs.
        output_path: Path to output LMDB database file.
        map_size: Maximum database size in bytes (default: 30GB).
        batch_size: Number of molecules per write transaction.
        on_conflict: "overwrite" | "skip" | "merge".
        verbose: If True (default), print progress to stdout.

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
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

                    if verbose:
                        elapsed = time.time() - start_time
                        tp = _total_processed(stats)
                        _print_progress(elapsed, tp,
                                        tp / elapsed if elapsed > 0 else 0,
                                        result, bt)

            # Final batch
            if batch:
                result, bt = _flush_batch(store, batch, on_conflict, stats)
                elapsed = time.time() - start_time
                tp = _total_processed(stats)
                if verbose:
                    _print_progress(elapsed, tp,
                                    tp / elapsed if elapsed > 0 else 0,
                                    result, bt)

    except lmdb.MapFullError:
        raise lmdb.MapFullError(
            f"LMDB map size exhausted. Increase map_size "
            f"(current: {map_size // 1024 ** 3}GB). "
            f"Use --map-size flag or set builder.lmdb.map_size_gb in config."
        )

    if verbose:
        total_time = time.time() - start_time
        processed = _total_processed(stats)
        speed = processed / total_time if total_time > 0 else 0
        print(
            f"\nDone. Processed: {processed} molecules ({stats}), "
            f"{total_conformers} conformers "
            f"in {total_time:.2f}s ({speed:.1f} mol/s)"
        )
    else:
        total_time = time.time() - start_time
        processed = _total_processed(stats)

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
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
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

    build_from_mapping(
        mapping, output, map_size, batch_size, on_conflict,
        xyz_path_column, inchi_column,
    )
