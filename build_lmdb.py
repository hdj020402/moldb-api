"""
Script to build LMDB database from XYZ files.
"""
import os
import argparse
from backend.lmdb import LMDBMoleculeStore
import pandas as pd

def main(xyz_dir: str, output_path: str, inchi_mapping_file: str, inchikey_column: str, inchi_column: str, map_size: int):
    """
    Build LMDB database from XYZ files.
    
    Args:
        xyz_dir: Directory containing XYZ files (named by InChIKey)
        output_path: Path to output LMDB database
        inchi_mapping_file: CSV file with InChIKey to InChI mapping
        inchikey_column: Name of the InChIKey column in the CSV file
        inchi_column: Name of the InChI column in the CSV file
        map_size: Maximum size of the database in bytes
    """
    # Initialize store
    store = LMDBMoleculeStore(output_path, map_size=map_size)
    
    # Load InChI mapping
    inchikey_to_inchi = {}
    if inchi_mapping_file and os.path.exists(inchi_mapping_file):
        print(f"Loading InChIKey to InChI mapping from {inchi_mapping_file}...")
        df = pd.read_csv(inchi_mapping_file)
        for _, row in df.iterrows():
            inchikey = row[inchikey_column]
            inchi = row[inchi_column]
            inchikey_to_inchi[inchikey] = inchi
    
    # Process XYZ files
    print(f"Processing XYZ files from {xyz_dir}...")
    count = 0
    mapped_count = 0
    
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
        
        # Store by InChI
        store.put(inchi, content)
        mapped_count += 1
        
        count += 1
        if count % 10000 == 0:
            print(f"Processed {count} files...")
    
    print(f"Done. Total: {count} files, {mapped_count} InChIs stored.")
    store.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build LMDB database from XYZ files")
    parser.add_argument("--xyz_dir", required=True, help="Directory containing XYZ files (named by InChIKey)")
    parser.add_argument("--output", default="molecules.lmdb", help="Output LMDB database path")
    parser.add_argument("--inchi_mapping", required=True, help="CSV file with InChIKey to InChI mapping")
    parser.add_argument("--inchikey_column", required=True, help="Name of the InChIKey column in the CSV file")
    parser.add_argument("--inchi_column", required=True, help="Name of the InChI column in the CSV file")
    parser.add_argument("--map_size", type=int, default=30 * 1024**3, help="Maximum size of the database in bytes (default: 30GB)")
    
    args = parser.parse_args()
    main(args.xyz_dir, args.output, args.inchi_mapping, args.inchikey_column, args.inchi_column, args.map_size)