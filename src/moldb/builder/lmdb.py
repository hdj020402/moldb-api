"""
Build LMDB database from XYZ file iterables or mapping files.

Two usage modes:

1. Stream mode (programmatic) — feed an iterable directly from a pipeline:
   >>> from moldb.builder.lmdb import build_lmdb_stream
   >>> items = [("InChI=1/...", [{"xyz": "xyz_content_1"}, {"xyz": "xyz_content_2"}]), ...]
   >>> stats = build_lmdb_stream(items, "molecules.lmdb")
   >>> stats = build_lmdb_stream(items, "molecules.lmdb", on_conflict="skip")

2. CLI mode (from mapping file) — existing disk-based workflow:
   $ moldb builder lmdb --mapping mapping.csv --output molecules.lmdb

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
import argparse
from typing import Iterable, Iterator
from ..core.lmdb import LMDBMoleculeStore, ConflictMode, ConformerData
import pandas as pd
from ..config.config import BuilderSettings


def build_lmdb_stream(
    items: Iterable[tuple[str, list[ConformerData]]],
    output_path: str,
    map_size: int = 30 * 1024 ** 3,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
) -> dict:
    """
    Build LMDB database from an iterable of (inchi, conformers) pairs.

    This is the core stream-based builder — it receives data in memory
    and writes directly to LMDB without any disk I/O for the XYZ content.
    Ideal for embedding in preprocessing pipelines.

    Args:
        items: Iterable of (inchi, conformers_list) pairs.
               Each inchi is a Fixed-H InChI string.
               Each conformers_list is a list of dicts with \"xyz\" key
               plus any optional metadata.
        output_path: Path to output LMDB database file.
        map_size: Maximum size of the database in bytes (default: 30GB).
        batch_size: Number of molecules per write transaction.
        on_conflict: How to handle existing keys:
            - "overwrite": Replace existing data (default).
            - "skip": Do nothing if key already exists.
            - "merge": Append conformers to existing entry.

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
    store = LMDBMoleculeStore(output_path, map_size=map_size, sync=False, writemap=True)

    batch: list[tuple[str, list[ConformerData]]] = []
    stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
    total_conformers = 0
    start_time = time.time()

    def _total_processed() -> int:
        return stats["written"] + stats["overwritten"] + stats["skipped"] + stats["merged"]

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
            _print_progress(elapsed, processed, speed, result, batch_time)

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
        _print_progress(elapsed, processed, speed, result, batch_time)

    store.close()

    total_time = time.time() - start_time
    processed = _total_processed()
    final_speed = processed / total_time if total_time > 0 else 0
    print(f"\nDone. Processed: {processed} molecules ({stats}), "
          f"{total_conformers} conformers "
          f"in {total_time:.2f}s ({final_speed:.1f} mol/s)")

    return {
        "processed": processed,
        "written": stats["written"],
        "overwritten": stats["overwritten"],
        "skipped": stats["skipped"],
        "merged": stats["merged"],
        "conformers": total_conformers,
        "time_seconds": total_time,
    }


def _print_progress(elapsed: float, processed: int, speed: float,
                    batch_result: dict, batch_time: float):
    """Print a progress line for a completed batch."""
    parts = [f"W:{batch_result['written']}", f"O:{batch_result['overwritten']}"]
    if batch_result.get("skipped"):
        parts.append(f"S:{batch_result['skipped']}")
    if batch_result.get("merged"):
        parts.append(f"M:{batch_result['merged']}")
    detail = ",".join(parts)
    print(f"[{elapsed:.1f}s] Total {processed} mols, "
          f"Speed: {speed:.1f} mol/s, "
          f"Batch [{detail}] in {batch_time:.2f}s")


def iter_mapping(
    mapping_file: str,
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
) -> Iterator[tuple[str, list[ConformerData]]]:
    """
    Generator that yields (inchi, conformers) from a CSV mapping file.

    This bridges the file-based workflow to the stream-based builder.
    XYZ content read from files is wrapped as {"xyz": content} dicts.

    Args:
        mapping_file: Path to CSV with xyz_path and inchi columns.
        xyz_path_column: Name of the column containing XYZ file paths.
        inchi_column: Name of the column containing Fixed-H InChI.

    Yields:
        (inchi, [conformer_dict]) tuples
    """
    builder = BuilderSettings()
    if xyz_path_column is None:
        xyz_path_column = builder.xyz_path_column
    if inchi_column is None:
        inchi_column = builder.inchi_column

    df = pd.read_csv(mapping_file)

    if xyz_path_column not in df.columns or inchi_column not in df.columns:
        raise ValueError(
            f"CSV must have '{xyz_path_column}' and '{inchi_column}' columns"
        )

    grouped = df.groupby(inchi_column)[xyz_path_column]

    for inchi, xyz_paths in grouped:
        conformers: list[ConformerData] = []
        for xyz_path in xyz_paths:
            with open(xyz_path, "r") as f:
                conformers.append({"xyz": f.read()})
        if conformers:
            yield (inchi, conformers)


def build_lmdb_from_mapping(
    mapping_file: str,
    output_path: str,
    map_size: int = 30 * 1024 ** 3,
    batch_size: int = 1000,
    on_conflict: ConflictMode = "overwrite",
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
) -> dict:
    """
    Build LMDB database from a CSV mapping file (convenience wrapper).

    Args:
        mapping_file: CSV file with xyz_path and inchi columns.
        output_path: Path to output LMDB database.
        map_size: Maximum database size in bytes (default: 30GB).
        batch_size: Molecules per write transaction.
        on_conflict: How to handle existing keys.
        xyz_path_column: Name of the xyz_path column in CSV.
        inchi_column: Name of the inchi column in CSV.

    Returns:
        dict with keys: processed, written, overwritten, skipped, merged,
        conformers, time_seconds
    """
    items = iter_mapping(mapping_file, xyz_path_column, inchi_column)
    return build_lmdb_stream(items, output_path, map_size, batch_size, on_conflict)


def run_build_lmdb():
    """CLI entry point for LMDB database building."""
    builder = BuilderSettings()

    parser = argparse.ArgumentParser(
        description="Build LMDB database from XYZ files with conformer support"
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="CSV file with xyz_path and fixed_h_inchi columns"
    )
    parser.add_argument(
        "--output",
        default="molecules.lmdb",
        help="Output LMDB database path"
    )
    parser.add_argument(
        "--map_size",
        type=int,
        default=30 * 1024 ** 3,
        help="Maximum size of the database in bytes (default: 30GB)"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1000,
        help="Number of molecules per write transaction"
    )
    parser.add_argument(
        "--on_conflict",
        default="overwrite",
        choices=["overwrite", "skip", "merge"],
        help="Conflict resolution strategy (default: overwrite)"
    )
    parser.add_argument(
        "--xyz_path_column",
        default=None,
        help=f"Name of the xyz_path column (default: {builder.xyz_path_column})"
    )
    parser.add_argument(
        "--inchi_column",
        default=None,
        help=f"Name of the fixed_h_inchi column (default: {builder.inchi_column})"
    )

    args = parser.parse_args()
    build_lmdb_from_mapping(
        args.mapping, args.output, args.map_size, args.batch_size,
        args.on_conflict, args.xyz_path_column, args.inchi_column,
    )


if __name__ == "__main__":
    run_build_lmdb()
