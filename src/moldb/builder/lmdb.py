"""
Script to build LMDB database from XYZ files.

CSV format (required):
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
from ..core.lmdb import LMDBMoleculeStore
import pandas as pd
from ..config.config import config


def main(mapping_file: str, output_path: str, map_size: int, batch_size: int = 1000):
    """
    Build LMDB database from XYZ files with conformer support.

    Args:
        mapping_file: CSV file with xyz_path and fixed_h_inchi columns
        output_path: Path to output LMDB database
        map_size: Maximum size of the database in bytes
        batch_size: Number of molecules to write in each transaction
    """
    # Initialize store — disable sync for faster writes
    store = LMDBMoleculeStore(output_path, map_size=map_size, sync=False, writemap=True)

    # Load mapping
    print(f"Loading mapping from {mapping_file}...")
    df = pd.read_csv(mapping_file)

    # Validate required columns
    if "xyz_path" not in df.columns or "fixed_h_inchi" not in df.columns:
        print("Error: CSV must have 'xyz_path' and 'fixed_h_inchi' columns")
        store.close()
        return

    # Group by InChI
    print("Grouping XYZ files by InChI...")
    grouped = df.groupby("fixed_h_inchi")["xyz_path"]

    total_molecules = grouped.ngroups
    total_conformers = len(df)
    print(f"Found {total_molecules} unique molecules with {total_conformers} total conformers")

    # Process in batches
    entries = []
    processed_molecules = 0
    processed_conformers = 0
    failed_files = 0
    start_time = time.time()

    for inchi, xyz_paths in grouped:
        conformers = []
        for xyz_path in xyz_paths:
            try:
                with open(xyz_path, "r") as f:
                    content = f.read()
                conformers.append(content)
                processed_conformers += 1
            except Exception as e:
                print(f"Error reading {xyz_path}: {e}")
                failed_files += 1
                continue

        if conformers:
            entries.append((inchi, conformers))
            processed_molecules += 1

        # Batch commit
        if len(entries) >= batch_size:
            batch_start = time.time()
            written = store.put_many_conformers(entries)
            batch_time = time.time() - batch_start
            entries = []

            # Stats
            elapsed = time.time() - start_time
            speed = processed_molecules / elapsed if elapsed > 0 else 0
            print(f"[{elapsed:.1f}s] Processed {processed_molecules}/{total_molecules} molecules, "
                  f"{processed_conformers} conformers, "
                  f"Speed: {speed:.1f} mol/s, "
                  f"Last batch: {written} in {batch_time:.2f}s")

    # Final batch
    if entries:
        batch_start = time.time()
        written = store.put_many_conformers(entries)
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        speed = processed_molecules / elapsed if elapsed > 0 else 0
        print(f"[{elapsed:.1f}s] Final batch: {written} molecules in {batch_time:.2f}s")

    total_time = time.time() - start_time
    final_speed = processed_molecules / total_time if total_time > 0 else 0
    print(f"\nDone. Total: {processed_molecules} molecules, {processed_conformers} conformers, "
          f"{failed_files} failed files in {total_time:.2f}s ({final_speed:.1f} mol/s)")
    store.close()


def run_build_lmdb():
    """Run the LMDB build process with configuration support."""
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
        default=config.get_lmdb_path(),
        help="Output LMDB database path"
    )
    parser.add_argument(
        "--map_size",
        type=int,
        default=30 * 1024**3,
        help="Maximum size of the database in bytes (default: 30GB)"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1000,
        help="Number of molecules per write transaction"
    )

    args = parser.parse_args()
    main(args.mapping, args.output, args.map_size, args.batch_size)


if __name__ == "__main__":
    run_build_lmdb()
