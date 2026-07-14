# moldb-api

High-performance molecular structure data storage and query service with conformer support.

## Features

- **Conformer-aware storage**: Store multiple conformers per molecule
- **Flexible metadata**: Each conformer carries arbitrary key-value pairs (energy, source, method, etc.)
- **Streaming writes**: Build databases directly from preprocessing pipelines without intermediate files
- **Conflict resolution**: `overwrite` / `skip` / `merge` strategies for incremental and streaming workflows
- **LMDB storage**: Memory-mapped, zero-copy reads, optimized for read-heavy workloads
- **RESTful API**: FastAPI-based query service

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

```text
Key: {fixed_h_inchi}::meta    → {"count": N}
Key: {fixed_h_inchi}::conf_0  → {"xyz": "...", "energy": -76.4, ...}
Key: {fixed_h_inchi}::conf_1  → {"xyz": "...", ...}
...
Key: {fixed_h_inchi}::conf_{N-1}  → {"xyz": "...", ...}
```

Each conformer value is a JSON object. The only reserved key is `"xyz"`;
all other keys (`energy`, `source`, `method`, etc.) are free-form and optional.

See [docs/DESIGN.md](docs/DESIGN.md) for the rationale behind the multi-key schema.

## Building the Database

### Method 1: Stream-based (recommended for pipelines)

Feed conformer data directly from a preprocessing pipeline — no intermediate files needed:

```python
from moldb.builder import build_stream

def my_pipeline(xyz_dir):
    """Your preprocessing logic."""
    for xyz_file in sorted(glob(f"{xyz_dir}/*.xyz")):
        for mol in parse_molecules(xyz_file):
            inchi = generate_fixed_h_inchi(mol)
            standardized = standardize_atoms(mol)
            yield (inchi, [{"xyz": standardized}])

build_stream(my_pipeline("./raw_xyzs/"), "molecules.lmdb")
```

### Method 2: Direct store API

```python
from moldb.store import LMDBMoleculeStore

store = LMDBMoleculeStore("molecules.lmdb")

# Store conformers (each is a dict with "xyz" key)
conformers = [
    {"xyz": "3\n\nO  0.000  0.000  0.000\nH  0.757  0.586  0.000\nH -0.757  0.586  0.000"},
    {"xyz": "3\n\nO  0.001  0.001  0.001\nH  0.758  0.587  0.001\nH -0.756  0.587  0.001",
     "energy": -76.4, "method": "B3LYP/6-31G*"},
]
store.put_conformers("InChI=1/H2O/h1H2", conformers)

# Query
data = store.get_conformers("InChI=1/H2O/h1H2")
print(f"Found {data['count']} conformers")
for conf in data["conformers"]:
    print(conf["xyz"][:50])

store.close()
```

### Method 3: CLI (from mapping file)

Prepare a CSV file with `xyz_path` and `fixed_h_inchi` columns:

```csv
xyz_path,fixed_h_inchi
/path/to/mol1_conf1.xyz,InChI=1/C3H7NO/.../f/h4H2
/path/to/mol1_conf2.xyz,InChI=1/C3H7NO/.../f/h4H2
/path/to/mol2_conf1.xyz,InChI=1/C3H7NO/.../f/h5H2
```

```bash
moldb builder --mapping mapping.csv --output molecules.lmdb
moldb builder --mapping new_data.csv --output molecules.lmdb --on-conflict skip
```

### Conflict Resolution (`on_conflict`)

When writing to an existing database, control what happens on key collisions:

| Mode | DB has key | DB lacks key |
| ---- | ---------- | ------------ |
| `overwrite` (default) | Replace all conformers | Write new |
| `skip` | Do nothing, keep old data | Write new |
| `merge` | Append new conformers to existing | Write new |

```python
# Incremental build: only write new molecules, skip existing
build_stream(batch_2, "molecules.lmdb", on_conflict="skip")

# Streaming: conformers arrive one at a time for the same molecule
for conf in streaming_source:
    build_stream([("InChI=1/A", [conf])], "molecules.lmdb", on_conflict="merge")
```

## Configuration

Copy the example config and edit as needed:

```bash
cp config/config.example.json config/config.json
```

All settings have reasonable defaults; the config file is optional.

## Running the API Service

```bash
# Start the API service (default port 8000)
moldb api

# Custom host, port, and database size
moldb api --host 0.0.0.0 --port 8000 --map-size 32212254720
```

## API Usage

### Query Single Molecule

```bash
curl "http://localhost:8000/molecule/InChI=1/H2O/h1H2"
```

Response:

```json
{
  "inchi": "InChI=1/H2O/h1H2",
  "count": 2,
  "conformers": [
    {
      "xyz": "3\n\nO  0.000  0.000  0.000\nH  0.757  0.586  0.000\nH -0.757  0.586  0.000"
    },
    {
      "xyz": "3\n\nO  0.001  0.001  0.001\nH  0.758  0.587  0.001\nH -0.756  0.587  0.001",
      "energy": -76.4,
      "method": "B3LYP/6-31G*"
    }
  ]
}
```

### Batch Query

```bash
curl -X POST http://localhost:8000/molecules/batch \
  -H "Content-Type: application/json" \
  -d '{"inchis": ["InChI=1/H2O/h1H2", "InChI=1/NOPE"]}'
```

Response:

```json
{
  "InChI=1/H2O/h1H2": {
    "inchi": "InChI=1/H2O/h1H2",
    "count": 2,
    "conformers": [
      {"xyz": "..."},
      {"xyz": "..."}
    ]
  },
  "InChI=1/NOPE": null
}
```

## Project Structure

```text
moldb-api/
├── pyproject.toml          # Package configuration
├── main.py                 # Development launcher
├── config/                 # Configuration
│   ├── config.example.json # Example config (copy to config.json)
│   └── config.json         # Local config (gitignored)
├── docs/                   # Documentation
│   ├── API_DOCUMENTATION.md
│   └── DESIGN.md           # Design philosophy (single-key vs multi-key)
├── tests/                  # Unit tests
│   ├── conftest.py
│   ├── test_store.py
│   ├── test_builder.py
│   ├── test_api.py
│   ├── test_config.py
│   └── test_cli.py
└── src/moldb/
    ├── __init__.py
    ├── cli.py              # CLI entry point
    ├── store.py            # LMDB storage implementation
    ├── server.py           # FastAPI application and endpoints
    ├── build.py            # Stream and mapping-file builders
    └── config.py           # Configuration management
```

## Performance Considerations

- **LMDB**: Memory-mapped reads, zero-copy access — ideal for large-scale deployments
- **Batch writes**: Use `put_many_conformers()` for efficient bulk imports
- **Streaming writes**: Use `build_stream()` with an iterable to avoid intermediate files
- **Conformer count**: No hard limit; tested with up to 1000 conformers per molecule
