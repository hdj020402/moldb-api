# moldb-api

High-performance molecular structure data storage and query service with conformer support.

## Features

- **Conformer-aware storage**: Store multiple conformers per molecule
- **Dual storage backends**: LMDB (read-heavy optimization) and SQLite (simple deployment)
- **High performance**: Support for millions of molecules and conformers
- **RESTful API**: FastAPI-based query service
- **Flexible data import**: CLI tool or direct API calls

## Important Note on InChI

**This database requires non-standard (Fixed-H) InChI** to distinguish tautomers.

Standard InChI (`InChI=1S/...`) treats tautomers as equivalent (e.g., `(H2,4,5)` indicates equivalent hydrogens). Non-standard InChI with Fixed-H layer specifies exact hydrogen positions.

**Format rules**:
- `InChI=1S/...` - Standard InChI (cannot have `/f/h` layer)
- `InChI=1/...` - Non-standard InChI (may have `/f/h` if molecule has ambiguous hydrogens)

**Examples**:
- Standard: `InChI=1S/H2O/h1H2`
- Non-standard (no ambiguous H): `InChI=1/H2O/h1H2`
- Non-standard Fixed-H (ambiguous H fixed): `InChI=1/C3H7NO/.../f/h4H2`

Note: Your database should use non-standard InChI (`InChI=1/...`) generated with Fixed-H option.

## Installation

```bash
# Create and activate a virtual environment
conda create -n moldb-api python=3.12
conda activate moldb-api

# Install the package
pip install -e .
```

## Storage Scheme

Each molecule's conformers are stored as separate key-value pairs:

```
Key: {fixed_h_inchi}::meta    → {"count": N}
Key: {fixed_h_inchi}::conf_0  → "xyz_string_0"
Key: {fixed_h_inchi}::conf_1  → "xyz_string_1"
...
Key: {fixed_h_inchi}::conf_{N-1}  → "xyz_string_{N-1}"
```

## Building the Database

### Method 1: CLI Tool

Prepare a CSV file with two columns: `xyz_path` and `fixed_h_inchi`:

```csv
xyz_path,fixed_h_inchi
/path/to/mol1_conf1.xyz,InChI=1/C3H7NO/.../f/h4H2
/path/to/mol1_conf2.xyz,InChI=1/C3H7NO/.../f/h4H2
/path/to/mol2_conf1.xyz,InChI=1/C3H7NO/.../f/h5H2
```

Build the database:

```bash
# LMDB backend
moldb builder lmdb --mapping conformers.csv --output molecules.lmdb

# SQLite backend
moldb builder sqlite --mapping conformers.csv --output molecules.db
```

### Method 2: Direct API Calls

```python
from moldb.core.lmdb import LMDBMoleculeStore

# Initialize store
store = LMDBMoleculeStore("molecules.lmdb")

# Store conformers
conformers = [
    "3\n\nO    0.000  0.000  0.000\nH    0.757  0.586  0.000\nH   -0.757  0.586  0.000",
    "3\n\nO    0.001  0.001  0.001\nH    0.758  0.587  0.001\nH   -0.756  0.587  0.001",
]
store.put_conformers("InChI=1/H2O/h1H2", conformers)

# Query conformers
data = store.get_conformers("InChI=1/H2O/h1H2")
print(f"Found {data['count']} conformers")

store.close()
```

## Running the API Service

```bash
# LMDB service (default port 8000)
moldb api lmdb

# SQLite service (default port 8001)
moldb api sqlite
```

Configuration via environment variables:

| Variable | Description |
|----------|-------------|
| `MOLECULES_LMDB_PATH` | LMDB database path |
| `MOLECULES_DB_PATH` | SQLite database path |
| `MOLECULES_API_HOST` | API host |
| `MOLECULES_LMDB_API_PORT` | LMDB API port |
| `MOLECULES_SQLITE_API_PORT` | SQLite API port |

## API Usage

### Query Single Molecule

```bash
# Note: InChI must match your database format (InChI=1/... or InChI=1S/...)
curl "http://localhost:8000/molecule/InChI=1/H2O/h1H2"
```

Response:
```json
{
  "inchi": "InChI=1/H2O/h1H2",
  "count": 2,
  "conformers": [
    "3\n\nO    0.000  0.000  0.000\nH    0.757  0.586  0.000\nH   -0.757  0.586  0.000",
    "3\n\nO    0.001  0.001  0.001\nH    0.758  0.587  0.001\nH   -0.756  0.587  0.001"
  ]
}
```

### Batch Query

```bash
curl -X POST http://localhost:8000/molecules/batch \
  -H "Content-Type: application/json" \
  -d '{"inchis": ["InChI=1/H2O/h1H2", "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3"]}'
```

Response:
```json
{
  "InChI=1/H2O/h1H2": {
    "inchi": "InChI=1/H2O/h1H2",
    "count": 2,
    "conformers": ["...", "..."]
  },
  "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3": null
}
```

## Project Structure

```
moldb-api/
├── pyproject.toml          # Package configuration
├── config.json             # Global configuration
├── main.py                 # Legacy entry point
└── src/moldb/
    ├── __init__.py
    ├── cli.py              # CLI entry point
    ├── core/               # Core storage implementations
    │   ├── lmdb.py         # LMDB storage
    │   └── sqlite.py       # SQLite storage
    ├── api/                # FastAPI services
    │   ├── lmdb.py         # LMDB API
    │   └── sqlite.py       # SQLite API
    ├── builder/            # Database building tools
    │   ├── lmdb.py         # LMDB builder
    │   └── sqlite.py       # SQLite builder
    ├── config/             # Configuration management
    │   └── config.py
    └── util/               # Utility functions
        └── query_molecule.py
```

## Performance Considerations

- **LMDB**: Optimized for read-heavy workloads, recommended for large-scale deployments
- **SQLite**: Simpler deployment, suitable for moderate workloads
- **Batch writes**: Use `put_many_conformers()` for efficient bulk imports
- **Conformer count**: No hard limit; tested with up to 1000 conformers per molecule
