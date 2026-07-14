#!/usr/bin/env python3
"""
moldb — Molecular structure data storage and querying service.

Usage:
    moldb [-c config] api [--host HOST] [--port PORT] [--map-size BYTES]
    moldb [-c config] builder --mapping CSV [options]
"""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="moldb",
        description="Molecular structure data storage and querying service",
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.json",
        help="Path to config file",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- api subcommand ---
    api = sub.add_parser("api", help="Run API service")
    api.add_argument("--host", default=None, help="Bind host (overrides config)")
    api.add_argument("--port", type=int, default=None,
                     help="Bind port (overrides config)")
    api.add_argument("--map-size", type=int, default=None,
                     help="LMDB map size in bytes (overrides config)")
    api.add_argument("--log-file", default=None,
                     help="Log file path (overrides config)")
    api.add_argument("--log-level", default=None,
                     choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                     help="Log level (overrides config)")

    # --- builder subcommand ---
    build = sub.add_parser("builder", help="Build database from XYZ files")
    build.add_argument("--mapping", default=None,
                        help="CSV file with xyz_path and fixed_h_inchi columns")
    build.add_argument("--output", default=None, help="Output LMDB database path")
    build.add_argument("--map-size", type=int, default=None,
                        help="LMDB map size in bytes")
    build.add_argument("--batch-size", type=int, default=None,
                        help="Molecules per write transaction")
    build.add_argument("--on-conflict", choices=["overwrite", "skip", "merge"],
                        default=None, help="Conflict resolution strategy")
    build.add_argument("--xyz-path-column", default=None,
                        help="CSV column name for XYZ file paths")
    build.add_argument("--inchi-column", default=None,
                        help="CSV column name for Fixed-H InChI")
    build.add_argument("--log-file", default=None,
                        help="Log file path (overrides config)")
    build.add_argument("--log-level", default=None,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log level (overrides config)")

    # --- info subcommand ---
    info = sub.add_parser("info", help="Show database statistics")
    info.add_argument("db_path", help="Path to LMDB database")
    info.add_argument("--map-size", type=int, default=None,
                      help="LMDB map size in bytes")

    args = parser.parse_args()

    if args.command == "api":
        from moldb.server import run_api
        run_api(
            host=args.host,
            port=args.port,
            map_size=args.map_size,
            config_path=args.config,
            log_file=args.log_file,
            log_level=args.log_level,
        )

    elif args.command == "info":
        from moldb.build import run_info
        run_info(
            db_path=args.db_path,
            map_size=args.map_size,
        )

    elif args.command == "builder":
        from moldb.build import run_build
        run_build(
            mapping=args.mapping,
            output=args.output,
            map_size=args.map_size,
            batch_size=args.batch_size,
            on_conflict=args.on_conflict,
            xyz_path_column=args.xyz_path_column,
            inchi_column=args.inchi_column,
            config_path=args.config,
            log_file=args.log_file,
            log_level=args.log_level,
        )


if __name__ == "__main__":
    main()
