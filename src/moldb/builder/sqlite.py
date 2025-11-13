"""
Script to build SQLite database from XYZ files.
"""
import os
import argparse
from ..core.sqlite import SQLiteMoleculeStore
import pandas as pd
import time
from ..config.config import config

def main(xyz_dir: str, output_path: str, inchi_mapping_file: str, inchikey_column: str, inchi_column: str):
    """
    Build SQLite database from XYZ files.
    
    Args:
        xyz_dir: Directory containing XYZ files (named by InChIKey)
        output_path: Path to output SQLite database
        inchi_mapping_file: CSV file with InChIKey to InChI mapping
        inchikey_column: Name of the InChIKey column in the CSV file
        inchi_column: Name of the InChI column in the CSV file
    """
    # Initialize store
    store = SQLiteMoleculeStore(output_path)
    store.init_db()
    
    # Load InChI mapping
    inchikey_to_inchi = {}
    if inchi_mapping_file and os.path.exists(inchi_mapping_file):
        print(f"Loading InChIKey to InChI mapping from {inchi_mapping_file}...")
        df = pd.read_csv(inchi_mapping_file)
        for _, row in df.iterrows():
            inchikey = row[inchikey_column]
            inchi = row[inchi_column]
            inchikey_to_inchi[inchikey] = inchi
    
    # Process XYZ files with batch support
    print(f"Processing XYZ files from {xyz_dir}...")
    entries = []
    count = 0
    mapped_count = 0
    batch_size = 10000  # Commit every 10000 entries
    
    for filename in os.listdir(xyz_dir):
        if not filename.endswith(".xyz"):
            continue
            
        inchikey = filename[:-4]  # remove .xyz
        filepath = os.path.join(xyz_dir, filename)
        
        # Get InChI from mapping
        inchi = inchikey_to_inchi.get(inchikey)
        if not inchi:
            print(f"Warning: No InChI mapping found for {inchikey}, skipping...")
            continue
        
        # Read file content
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            continue
        
        # Add to batch
        entries.append((inchi, content))
        mapped_count += 1
        
        # Batch commit
        if len(entries) >= batch_size:
            written = store.put_many(entries)
            entries = []
            print(f"Processed {count} files, stored {written} entries in batch")
        
        count += 1
        if count % 10000 == 0:
            print(f"Processed {count} files...")
    
    # Final batch
    if entries:
        written = store.put_many(entries)
        print(f"Final batch: stored {written} entries")
    
    print(f"Done. Total: {count} files, {mapped_count} InChIs stored.")

def run_build_sqlite():
    """Run the SQLite build process with configuration support."""
    parser = argparse.ArgumentParser(description="Build SQLite database from XYZ files")
    parser.add_argument("--xyz_dir", default=config.get_sqlite_xyz_dir(), help="Directory containing XYZ files (named by InChIKey)")
    parser.add_argument("--output", default=config.get_sqlite_path(), help="Output SQLite database path")
    parser.add_argument("--inchi_mapping", default=config.get_sqlite_inchi_mapping(), help="CSV file with InChIKey to InChI mapping")
    parser.add_argument("--inchikey_column", default=config.get_inchikey_column(), help="Name of the InChIKey column in the CSV file")
    parser.add_argument("--inchi_column", default=config.get_inchi_column(), help="Name of the InChI column in the CSV file")
    
    args = parser.parse_args()
        
    main(args.xyz_dir, args.output, args.inchi_mapping, args.inchikey_column, args.inchi_column)

if __name__ == "__main__":
    run_build_sqlite()