"""
Script to build LMDB database from XYZ files.
"""
import time
import os
import argparse
from backend.lmdb import LMDBMoleculeStore
import pandas as pd


def main(xyz_dir: str, output_path: str, inchi_mapping_file: str, 
         inchikey_column: str, inchi_column: str, map_size: int,
         batch_size: int = 50000):
    """
    Build LMDB database from XYZ files with write speed monitoring.
    
    Args:
        xyz_dir: Directory containing XYZ files (named by InChIKey)
        output_path: Path to output LMDB database
        inchi_mapping_file: CSV file with InChIKey to InChI mapping
        inchikey_column: Name of the InChIKey column in the CSV file
        inchi_column: Name of the InChI column in the CSV file
        map_size: Maximum size of the database in bytes
        batch_size: Number of entries to write in each transaction
    """
    # Initialize store — disable sync for faster writes (optional but recommended for bulk load)
    store = LMDBMoleculeStore(output_path, map_size=map_size, sync=False, writemap=True)
    
    # Load InChI mapping
    inchikey_to_inchi = {}
    if inchi_mapping_file and os.path.exists(inchi_mapping_file):
        print(f"Loading InChIKey to InChI mapping from {inchi_mapping_file}...")
        df = pd.read_csv(inchi_mapping_file)
        for _, row in df.iterrows():
            inchikey = row[inchikey_column]
            inchi = row[inchi_column]
            inchikey_to_inchi[inchikey] = inchi

    # Get list of XYZ files upfront for progress estimation
    all_xyz_files = [f for f in os.listdir(xyz_dir) if f.endswith(".xyz")]
    total_files = len(all_xyz_files)
    print(f"Found {total_files} XYZ files in {xyz_dir}")

    entries = []
    processed = 0
    stored = 0
    start_time = time.time()

    for filename in all_xyz_files:
        inchikey = filename[:-4]  # remove .xyz
        inchi = inchikey_to_inchi.get(inchikey)
        if not inchi:
            continue

        filepath = os.path.join(xyz_dir, filename)
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            continue

        entries.append((inchi, content))
        processed += 1

        # Batch commit
        if len(entries) >= batch_size:
            batch_start = time.time()
            written = store.put_many(entries)
            batch_time = time.time() - batch_start
            stored += written
            entries = []

            # Speed stats
            elapsed = time.time() - start_time
            speed = stored / elapsed if elapsed > 0 else 0
            print(f"[{elapsed:.1f}s] Processed {processed}/{total_files}, "
                  f"Stored {stored}, "
                  f"Speed: {speed:.1f} entries/sec, "
                  f"Last batch: {written} in {batch_time:.2f}s")

    # Final batch
    if entries:
        batch_start = time.time()
        written = store.put_many(entries)
        stored += written
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        speed = stored / elapsed if elapsed > 0 else 0
        print(f"[{elapsed:.1f}s] Final batch: {written} entries in {batch_time:.2f}s")

    total_time = time.time() - start_time
    final_speed = stored / total_time if total_time > 0 else 0
    print(f"\n✅ Done. Total: {processed} files processed, {stored} stored in {total_time:.2f}s "
          f"({final_speed:.1f} entries/sec)")
    store.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build LMDB database from XYZ files")
    parser.add_argument("--xyz_dir", required=True, help="Directory containing XYZ files (named by InChIKey)")
    parser.add_argument("--output", default="molecules.lmdb", help="Output LMDB database path")
    parser.add_argument("--inchi_mapping", required=True, help="CSV file with InChIKey to InChI mapping")
    parser.add_argument("--inchikey_column", required=True, help="Name of the InChIKey column in the CSV file")
    parser.add_argument("--inchi_column", required=True, help="Name of the InChI column in the CSV file")
    parser.add_argument("--map_size", type=int, default=30 * 1024**3, help="Maximum size of the database in bytes (default: 30GB)")
    parser.add_argument("--batch_size", type=int, default=50000, help="Number of entries per write transaction")
    
    args = parser.parse_args()
    main(args.xyz_dir, args.output, args.inchi_mapping, args.inchikey_column, args.inchi_column, args.map_size)