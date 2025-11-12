# API Documentation

## LMDB Backend Service

Base URL: `http://localhost:8000`

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
- `inchi` (string, required): InChI identifier

**Response (200):**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Error Responses:**
- 404: Molecule not found

### Add/Update Molecule

**POST /molecule**

Add or update molecule data.

**Request Body:**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Molecule data stored successfully"
}
```

**Error Responses:**
- 500: Failed to store molecule

### Delete Molecule

**DELETE /molecule/{inchi}**

Delete molecule data.

**Path Parameters:**
- `inchi` (string, required): InChI identifier

**Response (200):**
```json
{
  "status": "deleted",
  "message": "Molecule data deleted successfully"
}
```

**Error Responses:**
- 404: Molecule not found or delete failed

---

## SQLite Backend Service

Base URL: `http://localhost:8001`

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
- `inchi` (string, required): InChI identifier

**Response (200):**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Error Responses:**
- 404: Molecule not found

### Add/Update Molecule

**POST /molecule**

Add or update molecule data.

**Request Body:**
```json
{
  "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
  "content": "Molecule data content..."
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Molecule data stored successfully"
}
```

### Delete Molecule

**DELETE /molecule/{inchi}**

Delete molecule data.

**Path Parameters:**
- `inchi` (string, required): InChI identifier

**Response (200):**
```json
{
  "status": "deleted",
  "message": "Molecule data deleted successfully"
}
```

**Error Responses:**
- 404: Molecule not found or delete failed