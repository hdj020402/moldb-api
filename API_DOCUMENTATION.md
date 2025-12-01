# API Documentation

## LMDB Backend Service

Base URL: `http://localhost:8000` (default, can be customized in config.json)

### Health Check

**GET /**

Returns service status information.

**Response:**
```json
{
  "message": "moldb-api - LMDB Backend is running"
}
```

### Get Molecule by InChI

**GET /molecule/{inchi}**

Retrieve molecule data by InChI.

**Path Parameters:**
- `inchi` (string, required): InChI identifier (URL encoded)

**Note:**
InChI identifiers contain special characters that must be URL encoded when used in HTTP requests. 
For example, `InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1` should be encoded as `InChI%3D1S/C3H3N/c1-3-2-4%281%293/h3H%2C1H2/t3-%2C4%3F/m0/s1`.

**URL Encoding Examples:**

Python:
```python
import urllib.parse
inchi = "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1"
encoded_inchi = urllib.parse.quote(inchi, safe='')
# Result: InChI%3D1S/C3H3N/c1-3-2-4%281%293/h3H%2C1H2/t3-%2C4%3F/m0/s1
```

JavaScript:
```javascript
const inchi = "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1";
const encodedInchi = encodeURIComponent(inchi);
// Result: InChI%3D1S%2FC3H3N%2Fc1-3-2-4(1)3%2Fh3H%2C1H2%2Ft3-%2C4%3F%2Fm0%2Fs1
```

cURL:
```bash
# Using Python to encode
inchi="InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1"
encoded_inchi=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$inchi', safe=''))")
curl "http://localhost:8000/molecule/$encoded_inchi"
```

**Response (200):**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Error Responses:**
- 404: Molecule not found

### Batch Query Molecules by InChI

**POST /molecules/batch**

Retrieve multiple molecule data by InChI in a single request.

**Request Body:**
```json
{
  "inchis": [
    "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
    "InChI=1S/H2O/h1H2"
  ]
}
```

**Note:**
InChI identifiers should be properly URL encoded when sent in the request body. 
The helper function `query_molecules_batch` handles encoding automatically.

**Response (200):**
```json
{
  "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3": "Molecule data content...",
  "InChI=1S/H2O/h1H2": "Molecule data content...",
  "InChI=1S/C6H6/c1-2-4-6-5-3-1/h1-6H": null
}
```

**Response (422):**
- Validation error if the request body format is invalid

---

## SQLite Backend Service

Base URL: `http://localhost:8001` (default, can be customized in config.json)

### Health Check

**GET /**

Returns service status information.

**Response:**
```json
{
  "message": "moldb-api - SQLite Backend is running"
}
```

### Get Molecule by InChI

**GET /molecule/{inchi}**

Retrieve molecule data by InChI.

**Path Parameters:**
- `inchi` (string, required): InChI identifier (URL encoded)

**Note:**
InChI identifiers contain special characters that must be URL encoded when used in HTTP requests. 
For example, `InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1` should be encoded as `InChI%3D1S/C3H3N/c1-3-2-4%281%293/h3H%2C1H2/t3-%2C4%3F/m0/s1`.

**URL Encoding Examples:**

Python:
```python
import urllib.parse
inchi = "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1"
encoded_inchi = urllib.parse.quote(inchi, safe='')
# Result: InChI%3D1S/C3H3N/c1-3-2-4%281%293/h3H%2C1H2/t3-%2C4%3F/m0/s1
```

JavaScript:
```javascript
const inchi = "InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1";
const encodedInchi = encodeURIComponent(inchi);
// Result: InChI%3D1S%2FC3H3N%2Fc1-3-2-4(1)3%2Fh3H%2C1H2%2Ft3-%2C4%3F%2Fm0%2Fs1
```

cURL:
```bash
# Using Python to encode
inchi="InChI=1S/C3H3N/c1-3-2-4(1)3/h3H,1H2/t3-,4?/m0/s1"
encoded_inchi=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$inchi', safe=''))")
curl "http://localhost:8000/molecule/$encoded_inchi"
```

**Response (200):**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Error Responses:**
- 404: Molecule not found