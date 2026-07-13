#!/usr/bin/env python3
"""
moldb — Molecular structure data storage and querying service.

Usage:
    moldb [-c config] api --backend lmdb|sqlite
    moldb [-c config] builder --backend lmdb|sqlite [options]
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="moldb",
        description="Molecular structure data storage and querying service",
    )
    parser.add_argument("-c", "--config", default="config/config.json",
                        help="Path to config file")

    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="Run API service")
    api.add_argument("--backend", choices=["lmdb", "sqlite"], required=True,
                     help="Storage backend")

    build = sub.add_parser("builder", help="Build database from XYZ files",
                           add_help=False)
    build.add_argument("--backend", choices=["lmdb", "sqlite"], required=True,
                       help="Storage backend")

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
