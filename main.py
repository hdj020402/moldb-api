#!/usr/bin/env python3
"""
Main entry point for moldb-api (backward compatibility).

For new usage, install the package and use the 'moldb' command:
    pip install -e .
    moldb api lmdb
    moldb builder lmdb --mapping conformers.csv

Usage (legacy):
    python main.py api lmdb       - Run LMDB API service
    python main.py api sqlite     - Run SQLite API service
    python main.py builder lmdb   - Build LMDB database
    python main.py builder sqlite - Build SQLite database

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import sys
import os

# Add src to path so we can import moldb modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the CLI
from moldb.cli import main

if __name__ == "__main__":
    main()
