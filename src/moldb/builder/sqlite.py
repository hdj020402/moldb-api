"""
Build SQLite database from XYZ file iterables or mapping files.

Two usage modes:

1. Stream mode (programmatic) — feed an iterable directly from a pipeline:
   >>> from moldb.builder.sqlite import build_sqlite_stream
   >>> items = [("InChI=1/...", [{"xyz": "xyz_content_1"}, {"xyz": "xyz_content_2"}]), ...]
   >>> stats = build_sqlite_stream(items, "molecules.db")
   >>> stats = build_sqlite_stream(items, "molecules.db", on_conflict="skip")

2. CLI mode (from mapping file) — existing disk-based workflow:
   $ moldb builder --backend sqlite --mapping mapping.csv --output molecules.db

CSV format for CLI mode (required):
    xyz_path,fixed_h_inchi
    /path/to/mol1_conf1.xyz,InChI=1/C3H7NO/.../f/h4H2
    /path/to/mol1_conf2.xyz,InChI=1/C3H7NO/.../f/h4H2
    /path/to/mol2_conf1.xyz,InChI=1/C3H7NO/.../f/h5H2

The CSV is grouped by fixed_h_inchi, and all XYZ files for the same InChI
are stored as conformers of that molecule.

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option.
"""
import argparse
import time
from typing import Iterable

from .common import print_progress, iter_mapping
from ..core.sqlite import SQLiteMoleculeStore, ConflictMode, ConformerData
from ..config.config import BuilderSettings


def build_sqlite_stream(
    items: Iterable[tuple[str, list[ConformerData]]],
    output_path: str,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
) -> dict:
    """
    Build SQLite database from an iterable of (inchi, conformers) pairs.

    This is the core stream-based builder — it receives data in memory
    and writes directly to SQLite without any disk I/O for the XYZ content.
    Ideal for embedding in preprocessing pipelines.

    Args:
        items: Iterable of (inchi, conformers_list) pairs.
               Each inchi is a Fixed-H InChI string.
               Each conformers_list is a list of dicts with "xyz" key
               plus any optional metadata.
        output_path: Path to output SQLite database file.
        batch_size: Number of molecules per write transaction.
        on_conflict: How to handle existing keys:
            - "overwrite": Replace existing data (default).
            - "skip": Do nothing if key already exists.
            - "merge": Append conformers to existing entry.

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
    batch: list[tuple[str, list[ConformerData]]] = []
    stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
    total_conformers = 0
    start_time = time.time()

    def _total_processed() -> int:
        return stats["written"] + stats["overwritten"] + stats["skipped"] + stats["merged"]

    with SQLiteMoleculeStore(output_path) as store:
        store.init_db()

        for inchi, conformers in items:
            if not conformers:
                continue

            batch.append((inchi, conformers))
            total_conformers += len(conformers)

            if len(batch) >= batch_size:
                batch_start = time.time()
                result = store.put_many_conformers(batch, on_conflict=on_conflict)
                for key in ("written", "overwritten", "skipped", "merged"):
                    stats[key] += result[key]
                batch_time = time.time() - batch_start
                batch.clear()

                elapsed = time.time() - start_time
                processed = _total_processed()
                speed = processed / elapsed if elapsed > 0 else 0
                print_progress(elapsed, processed, speed, result, batch_time)

        # Final batch
        if batch:
            batch_start = time.time()
            result = store.put_many_conformers(batch, on_conflict=on_conflict)
            for key in ("written", "overwritten", "skipped", "merged"):
                stats[key] += result[key]
            batch_time = time.time() - batch_start
            elapsed = time.time() - start_time
            processed = _total_processed()
            speed = processed / elapsed if elapsed > 0 else 0
            print_progress(elapsed, processed, speed, result, batch_time)

    total_time = time.time() - start_time
    processed = _total_processed()
    final_speed = processed / total_time if total_time > 0 else 0
    print(
        f"\nDone. Processed: {processed} molecules ({stats}), "
        f"{total_conformers} conformers "
        f"in {total_time:.2f}s ({final_speed:.1f} mol/s)"
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


def build_sqlite_from_mapping(
    mapping_file: str,
    output_path: str,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
) -> dict:
    """
    Build SQLite database from a CSV mapping file (convenience wrapper).

    Args:
        mapping_file: CSV file with xyz_path and inchi columns.
        output_path: Path to output SQLite database.
        batch_size: Molecules per write transaction.
        on_conflict: How to handle existing keys.
        xyz_path_column: Name of the xyz_path column in CSV.
        inchi_column: Name of the inchi column in CSV.

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
    items = iter_mapping(mapping_file, xyz_path_column, inchi_column)
    return build_sqlite_stream(items, output_path, batch_size, on_conflict)


def run_build_sqlite(args: list[str] | None = None):
    """CLI entry point for SQLite database building."""
    builder = BuilderSettings()

    parser = argparse.ArgumentParser(
        description="Build SQLite database from XYZ files with conformer support"
    )
    parser.add_argument(
        "--mapping",
        default=builder.mapping_file,
        help="CSV file with xyz_path and fixed_h_inchi columns",
    )
    parser.add_argument(
        "--output",
        default=builder.sqlite_path,
        help="Output SQLite database path",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=builder.batch_size,
        help=f"Number of molecules per write transaction (default: {builder.batch_size})",
    )
    parser.add_argument(
        "--on_conflict",
        default=builder.on_conflict,
        choices=["overwrite", "skip", "merge"],
        help=f"Conflict resolution strategy (default: {builder.on_conflict})",
    )
    parser.add_argument(
        "--xyz_path_column",
        default=None,
        help=f"Name of the xyz_path column (default: {builder.xyz_path_column})",
    )
    parser.add_argument(
        "--inchi_column",
        default=None,
        help=f"Name of the fixed_h_inchi column (default: {builder.inchi_column})",
    )

    parsed = parser.parse_args(args)
    if not parsed.mapping:
        parser.error(
            "--mapping is required (or set builder.mapping.file in config.json)"
        )
    build_sqlite_from_mapping(
        parsed.mapping,
        parsed.output,
        parsed.batch_size,
        parsed.on_conflict,
        parsed.xyz_path_column,
        parsed.inchi_column,
    )
