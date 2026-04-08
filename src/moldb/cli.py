#!/usr/bin/env python3
"""
CLI entry point for moldb-api.

Usage:
    moldb api lmdb       - Run LMDB API service
    moldb api sqlite     - Run SQLite API service
    moldb builder lmdb   - Build LMDB database from XYZ files
    moldb builder sqlite - Build SQLite database from XYZ files

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import sys


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("moldb - Molecular structure data storage and querying service")
        print("")
        print("Usage:")
        print("  moldb api lmdb       - Run LMDB API service")
        print("  moldb api sqlite     - Run SQLite API service")
        print("  moldb builder lmdb   - Build LMDB database from XYZ files")
        print("  moldb builder sqlite - Build SQLite database from XYZ files")
        print("")
        print("Note: InChI must be Fixed-H InChI to distinguish tautomers.")
        print("")
        return

    command = sys.argv[1]

    if command == "api":
        if len(sys.argv) < 3:
            print("Usage: moldb api [lmdb|sqlite]")
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
            print("Usage: moldb api [lmdb|sqlite]")

    elif command == "builder":
        if len(sys.argv) < 3:
            print("Usage: moldb builder [lmdb|sqlite]")
            return

        subcommand = sys.argv[2]
        # Remove the first two arguments before passing to builder
        sys.argv = [sys.argv[0]] + sys.argv[3:]

        if subcommand == "lmdb":
            from moldb.builder.lmdb import run_build_lmdb
            run_build_lmdb()
        elif subcommand == "sqlite":
            from moldb.builder.sqlite import run_build_sqlite
            run_build_sqlite()
        else:
            print(f"Unknown builder subcommand: {subcommand}")
            print("Usage: moldb builder [lmdb|sqlite]")

    else:
        print(f"Unknown command: {command}")
        print("")
        print("Usage:")
        print("  moldb api lmdb       - Run LMDB API service")
        print("  moldb api sqlite     - Run SQLite API service")
        print("  moldb builder lmdb   - Build LMDB database from XYZ files")
        print("  moldb builder sqlite - Build SQLite database from XYZ files")
        print("")


if __name__ == "__main__":
    main()
