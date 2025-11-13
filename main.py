#!/usr/bin/env python3
"""
Main entry point for moldb-api.
Supports running both LMDB and SQLite services, and building databases.
"""

import sys
import os

# Add src to path so we can import moldb modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """Main entry point."""
    # If no arguments provided, show usage
    if len(sys.argv) < 2:
        print("moldb-api - Molecular structure data storage and querying service")
        print("")
        print("Usage:")
        print("  python main.py api lmdb     - Run LMDB API service")
        print("  python main.py api sqlite   - Run SQLite API service")
        print("  python main.py builder lmdb   - Build LMDB database from XYZ files")
        print("  python main.py builder sqlite - Build SQLite database from XYZ files")
        print("")
        return

    # Import the required modules only when needed
    command = sys.argv[1]
    
    if command == "api":
        if len(sys.argv) < 3:
            print("Usage: python main.py api [lmdb|sqlite]")
            return
            
        subcommand = sys.argv[2]
        if subcommand == "lmdb":
            from moldb.api.lmdb import run_lmdb_api
            run_lmdb_api()
        elif subcommand == "sqlite":
            from moldb.api.sqlite import run_sqlite_api
            run_sqlite_api()
        else:
            print(f"Unknown API subcommand: {subcommand}")
            print("Usage: python main.py api [lmdb|sqlite]")
    elif command == "builder":
        if len(sys.argv) < 3:
            print("Usage: python main.py builder [lmdb|sqlite]")
            return
            
        subcommand = sys.argv[2]
        # Remove the first two arguments (command and subcommand) before passing to builder
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        
        if subcommand == "lmdb":
            from moldb.builder.lmdb import run_build_lmdb
            run_build_lmdb()
        elif subcommand == "sqlite":
            from moldb.builder.sqlite import run_build_sqlite
            run_build_sqlite()
        else:
            print(f"Unknown builder subcommand: {subcommand}")
            print("Usage: python main.py builder [lmdb|sqlite]")
    else:
        print(f"Unknown command: {command}")
        print("")
        print("Usage:")
        print("  python main.py api lmdb     - Run LMDB API service")
        print("  python main.py api sqlite   - Run SQLite API service")
        print("  python main.py builder lmdb   - Build LMDB database from XYZ files")
        print("  python main.py builder sqlite - Build SQLite database from XYZ files")
        print("")

if __name__ == "__main__":
    main()