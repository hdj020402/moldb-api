# API Documentation

## Important Note

**This database requires non-standard (Fixed-H) InChI** to distinguish tautomers.

**Format rules**:

- `InChI=1S/...` - Standard InChI (cannot have `/f/h` layer)
- `InChI=1/...` - Non-standard InChI (may have `/f/h` if molecule has ambiguous hydrogens)

Standard InChI treats tautomers as equivalent, which would incorrectly merge different molecular structures. Non-standard InChI with Fixed-H layer specifies exact hydrogen positions.

---

## API Service

Base URL: `http://localhost:8000` (default)

### Health Check

#### GET /

Returns service status information.

**Response:**

```json
{
  "message": "moldb-api is running",
  "version": "0.3.0"
}
```

### Get Molecule by InChI

#### POST /molecule

Retrieve all conformers for a molecule by Fixed-H InChI.

**Request Body:**

```json
{
  "inchi": "InChI=1/H2O/h1H2"
}
```

**Response (200):**

```json
{
  "InChI=1/H2O/h1H2": {
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
}
```

Each conformer is a JSON object with a required `"xyz"` key containing the XYZ content.
Additional keys (`energy`, `source`, `method`, etc.) are optional and stored as-is.

If the molecule is not found, the response value for that InChI key will be `null`:

```json
{
  "InChI=1/NOPE": null
}
```

### Batch Query Molecules

#### POST /molecules/batch

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
    "conformers": [
      {"xyz": "..."},
      {"xyz": "..."}
    ]
  },
  "InChI=1/C2H6O/c1-2-3/h3H,2H2,1H3": null
}
```

Note: `null` indicates the molecule was not found.
