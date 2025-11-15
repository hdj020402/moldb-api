# moldb-api

This project provides a high-performance service for storing and querying molecular structure data from XYZ files. It supports two storage backends:

1. LMDB (Lightning Memory-Mapped Database) - Optimized for read-heavy workloads
2. SQLite - Simpler deployment with good performance for most use cases

## Features

- High-performance random access to molecular data
- Support for 2 million+ XYZ files
- FastAPI-based REST API for querying data (read-only)
- Support for InChI-based queries only
- Extensible design for future enhancements
- Batch insert support with `put_many` method for improved write performance (builder only)

## Project Structure

```
moldb-api/
├── config.json             # Configuration file
├── main.py                 # Main entry point
├── README.md               # This file
├── API_DOCUMENTATION.md    # API documentation
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore file
└── src/
    └── moldb/
        ├── __init__.py
        ├── core/           # Core storage implementations
        │   ├── __init__.py
        │   ├── lmdb.py     # LMDB storage implementation
        │   └── sqlite.py   # SQLite storage implementation
        ├── api/            # API services
        │   ├── __init__.py
        │   ├── lmdb.py     # FastAPI service for LMDB backend
        │   └── sqlite.py   # FastAPI service for SQLite backend
        ├── builder/        # Database building tools
        │   ├── __init__.py
        │   ├── lmdb.py     # Script to build LMDB database
        │   └── sqlite.py   # Script to build SQLite database
        ├── config/         # Configuration module
        │   ├── __init__.py
        │   └── config.py   # Configuration implementation
        └── util/           # Utility functions
            ├── __init__.py
            └── query_molecule.py  # Helper function to query molecule data
```

## Installation

```bash
# Create and activate a virtual environment
conda create -n moldb-api python=3.12
conda activate moldb-api

# Install required dependencies
pip install -r requirements.txt
```

## Building the Database

### LMDB Backend

```bash
# Build the LMDB database from XYZ files
# Note: Requires a CSV file containing InChIKey and InChI columns
python main.py builder lmdb
```

You can customize the build parameters by:
1. Setting command line arguments: `python main.py builder lmdb --xyz_dir ./data/xyz_files --output molecules.lmdb --inchi_mapping inchi_mapping.csv --inchikey_column inchikey --inchi_column inchi`
2. Setting parameters in the `config.json` file

### SQLite Backend

```bash
# Build the SQLite database from XYZ files
# Note: Requires a CSV file containing InChIKey and InChI columns
python main.py builder sqlite
```

You can customize the build parameters by:
1. Setting command line arguments: `python main.py builder sqlite --xyz_dir ./data/xyz_files --output molecules.db --inchi_mapping inchi_mapping.csv --inchikey_column inchikey --inchi_column inchi`
2. Setting parameters in the `config.json` file

## Running the Services

### LMDB Service

```bash
# Start the LMDB-based service (port 8000)
python main.py api lmdb
```

You can customize the database path and other parameters by:
1. Setting environment variables:
   - `MOLECULES_LMDB_PATH` - Database path
   - `MOLECULES_API_HOST` - Service host
   - `MOLECULES_LMDB_API_PORT` - Service port
2. Setting parameters in the `config.json` file

### SQLite Service

```bash
# Start the SQLite-based service (port 8001)
python main.py api sqlite
```

You can customize the database path and other parameters by:
1. Setting environment variables:
   - `MOLECULES_DB_PATH` - Database path
   - `MOLECULES_API_HOST` - Service host
   - `MOLECULES_SQLITE_API_PORT` - Service port
2. Setting parameters in the `config.json` file

## API Usage

### Query by InChI

```bash
# LMDB service
curl http://localhost:8000/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3

# SQLite service
curl http://localhost:8001/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3
```

### Using the query_molecule helper function

Python:
```python
from moldb.util.query_molecule import query_molecule

# Query molecule data (automatically handles URL encoding)
data = query_molecule("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")

if data:
    print(f"Content: {data['content']}")
else:
    print("Molecule not found")
```