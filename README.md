# moldb-api

This project provides a high-performance service for storing and querying molecular structure data from XYZ files. It supports two storage backends:

1. LMDB (Lightning Memory-Mapped Database) - Optimized for read-heavy workloads
2. SQLite - Simpler deployment with good performance for most use cases

## Features

- High-performance random access to molecular data
- Support for 2 million+ XYZ files
- FastAPI-based REST API for querying and updating data
- Support for InChI-based queries only
- Extensible design for future enhancements

## Project Structure

```
mol-database/
├── data/
│   └── xyz_files/          # Original XYZ files (InChIKey.xyz)
├── backend/
│   ├── __init__.py         # Package init
│   ├── lmdb.py             # LMDB storage implementation
│   └── sqlite.py           # SQLite storage implementation
├── service/
│   ├── __init__.py         # Package init
│   ├── lmdb_api.py         # FastAPI service for LMDB backend
│   └── sqlite_api.py       # FastAPI service for SQLite backend
├── build_lmdb.py           # Script to build LMDB database
├── build_sqlite.py         # Script to build SQLite database
├── API_DOCUMENTATION.md    # API documentation
├── DEVELOPMENT_LOG.md      # Development log
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Installation

```bash
# Install required dependencies
pip install -r requirements.txt
```

## Building the Database

### LMDB Backend

```bash
# Build the LMDB database from XYZ files
# Note: Requires a CSV file containing InChIKey and InChI columns
python build_lmdb.py --xyz_dir ./data/xyz_files --output molecules.lmdb --inchi_mapping inchi_mapping.csv --inchikey_column inchikey --inchi_column inchi
```

### SQLite Backend

```bash
# Build the SQLite database from XYZ files
# Note: Requires a CSV file containing InChIKey and InChI columns
python build_sqlite.py --xyz_dir ./data/xyz_files --output molecules.db --inchi_mapping inchi_mapping.csv --inchikey_column inchikey --inchi_column inchi
```

## Running the Services

### LMDB Service

```bash
# Start the LMDB-based service (port 8000)
python service/lmdb_api.py
```

### SQLite Service

```bash
# Start the SQLite-based service (port 8001)
python service/sqlite_api.py
```

## API Usage

### Query by InChI

```bash
# LMDB service
curl http://localhost:8000/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3

# SQLite service
curl http://localhost:8001/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3
```

### Add/Update Molecule Data

```bash
# LMDB service
curl -X POST http://localhost:8000/molecule \
  -H "Content-Type: application/json" \
  -d '{"inchi":"InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3","content":"3\n\nC 0 0 0\nH 1 0 0\nH -1 0 0"}'

# SQLite service
curl -X POST http://localhost:8001/molecule \
  -H "Content-Type: application/json" \
  -d '{"inchi":"InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3","content":"3\n\nC 0 0 0\nH 1 0 0\nH -1 0 0"}'
```

### Delete Molecule Data

```bash
# LMDB service
curl -X DELETE http://localhost:8000/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3

# SQLite service
curl -X DELETE http://localhost:8001/molecule/InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3
```