#!/usr/bin/env python3
"""
moldb — Molecular structure data storage and querying service.

Usage:
    moldb [-c config] api lmdb
    moldb [-c config] api sqlite
    moldb [-c config] builder lmdb [options]
    moldb [-c config] builder sqlite [options]

Note: Use non-standard InChI (InChI=1/...) with Fixed-H option to distinguish tautomers.
Standard InChI (InChI=1S/...) cannot have /f/h layer.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main():
    parser = argparse.ArgumentParser(
        prog="moldb",
        description="Molecular structure data storage and querying service",
    )
    parser.add_argument("-c", "--config", default="config/config.json",
                        help="Path to config file")

    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="Run API service")
    api_sub = api.add_subparsers(dest="backend", required=True)
    api_sub.add_parser("lmdb", help="LMDB backend")
    api_sub.add_parser("sqlite", help="SQLite backend")

    build = sub.add_parser("builder", help="Build database from XYZ files",
                           add_help=False)
    build_sub = build.add_subparsers(dest="backend", required=True)
    build_sub.add_parser("lmdb", help="LMDB backend", add_help=False)
    build_sub.add_parser("sqlite", help="SQLite backend", add_help=False)

    args, remaining = parser.parse_known_args()
    os.environ["MOLDB_CONFIG"] = args.config

    if args.command == "api":
        if args.backend == "lmdb":
            from moldb.api.lmdb import run_lmdb_api
            run_lmdb_api()
        else:
            from moldb.api.sqlite import run_sqlite_api
            run_sqlite_api()

    elif args.command == "builder":
        sys.argv = [sys.argv[0]] + remaining
        if args.backend == "lmdb":
            from moldb.builder.lmdb import run_build_lmdb
            run_build_lmdb()
        else:
            from moldb.builder.sqlite import run_build_sqlite
            run_build_sqlite()


if __name__ == "__main__":
    main()
