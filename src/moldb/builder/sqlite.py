"""
Script to build SQLite database from XYZ files.

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
from ..core.sqlite import SQLiteMoleculeStore
import pandas as pd
from ..config.config import config


def main(mapping_file: str, output_path: str, batch_size: int = 1000,
         xyz_path_column: str = None, inchi_column: str = None):
    """
    Build SQLite database from XYZ files with conformer support.

    Args:
        mapping_file: CSV file with xyz_path and fixed_h_inchi columns
        output_path: Path to output SQLite database
        batch_size: Number of molecules to write in each transaction
        xyz_path_column: Name of the xyz_path column in CSV
        inchi_column: Name of the fixed_h_inchi column in CSV
    """
    # Use config values if not provided
    if xyz_path_column is None:
        xyz_path_column = config.get_xyz_path_column()
    if inchi_column is None:
        inchi_column = config.get_inchi_column()

    # Initialize store
    store = SQLiteMoleculeStore(output_path)
    store.init_db()

    # Load mapping
    print(f"Loading mapping from {mapping_file}...")
    df = pd.read_csv(mapping_file)

    # Validate required columns
    if xyz_path_column not in df.columns or inchi_column not in df.columns:
        print(f"Error: CSV must have '{xyz_path_column}' and '{inchi_column}' columns")
        return

    # Group by InChI
    print(f"Grouping XYZ files by {inchi_column}...")
    grouped = df.groupby(inchi_column)[xyz_path_column]

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


def run_build_sqlite():
    """Run the SQLite build process with configuration support."""
    parser = argparse.ArgumentParser(
        description="Build SQLite database from XYZ files with conformer support"
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="CSV file with xyz_path and fixed_h_inchi columns"
    )
    parser.add_argument(
        "--output",
        default=config.get_sqlite_path(),
        help="Output SQLite database path"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1000,
        help="Number of molecules per write transaction"
    )
    parser.add_argument(
        "--xyz_path_column",
        default=None,
        help=f"Name of the xyz_path column (default: {config.get_xyz_path_column()})"
    )
    parser.add_argument(
        "--inchi_column",
        default=None,
        help=f"Name of the fixed_h_inchi column (default: {config.get_inchi_column()})"
    )

    args = parser.parse_args()
    main(args.mapping, args.output, args.batch_size,
         args.xyz_path_column, args.inchi_column)


if __name__ == "__main__":
    run_build_sqlite()
