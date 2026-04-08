# API Documentation

## Important Note

**This database requires non-standard (Fixed-H) InChI** to distinguish tautomers.

**Format rules**:
- `InChI=1S/...` - Standard InChI (cannot have `/f/h` layer)
- `InChI=1/...` - Non-standard InChI (may have `/f/h` if molecule has ambiguous hydrogens)

Standard InChI treats tautomers as equivalent, which would incorrectly merge different molecular structures. Non-standard InChI with Fixed-H layer specifies exact hydrogen positions.

---

## LMDB Backend Service

Base URL: `http://localhost:8000` (default)

### Health Check

**GET /**

Returns service status information.

**Response:**
```json
{
  "message": "moldb-api - LMDB Backend is running",
  "version": "2.0.0"
}
```

### Get Molecule by InChI

**GET /molecule/{inchi}**

Retrieve all conformers for a molecule by Fixed-H InChI.

**Path Parameters:**
- `inchi` (string, required): Fixed-H InChI identifier (URL encoded)

**Note:**
InChI identifiers contain special characters that must be URL encoded when used in HTTP requests.

**URL Encoding Examples:**

Python:
```python
import urllib.parse
inchi = "InChI=1/H2O/h1H2"  # non-standard (Fixed-H) InChI
encoded_inchi = urllib.parse.quote(inchi, safe='')
```

cURL:
```bash
# URL encode the InChI before sending
inchi="InChI=1/H2O/h1H2"
encoded_inchi=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$inchi', safe=''))")
curl "http://localhost:8000/molecule/$encoded_inchi"
```

**Response (200):**
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

**Error Responses:**
- 404: Molecule not found

### Batch Query Molecules

**POST /molecules/batch**

Retrieve multiple molecules' conformers in a single request.

**Request Body:**
```json
{
  "inchis": [
    "InChI=1/H2O/h1H2",
    "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3"
  ]
}
```

**Response (200):**
```json
{
  "InChI=1/H2O/h1H2": {
    "inchi": "InChI=1/H2O/h1H2",
    "count": 2,
    "conformers": ["xyz_string_1", "xyz_string_2"]
  },
  "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3": null
}
```

Note: `null` indicates the molecule was not found.

---

## SQLite Backend Service

Base URL: `http://localhost:8001` (default)

The SQLite backend has identical API endpoints to the LMDB backend.

### Health Check

**GET /**

**Response:**
```json
{
  "message": "moldb-api - SQLite Backend is running",
  "version": "2.0.0"
}
```

### Get Molecule by InChI

**GET /molecule/{inchi}**

Same as LMDB backend.

### Batch Query Molecules

**POST /molecules/batch**

Same as LMDB backend.

---

## Using the Python Helper

```python
from moldb.util.query_molecule import query_molecule, query_molecules_batch

# Query single molecule (use the InChI format from your database)
data = query_molecule("InChI=1/H2O/h1H2")
if data:
    print(f"Found {data['count']} conformers")
    for i, conf in enumerate(data['conformers']):
        print(f"Conformer {i}: {conf[:50]}...")

# Batch query
results = query_molecules_batch([
    "InChI=1/H2O/h1H2",
    "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3"
])

for inchi, data in results.items():
    if data:
        print(f"{inchi}: {data['count']} conformers")
    else:
        print(f"{inchi}: not found")
```
