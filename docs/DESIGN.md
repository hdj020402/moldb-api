# Design Philosophy

## Storage Schema: Multi-Key vs Single-Key

The database stores molecular structure data, mapping Fixed-H InChI identifiers to
lists of 3D conformers. The fundamental access pattern is:

> **One InChI → all conformers of that molecule**

### The Two Approaches

**Single-key** — one LMDB entry per molecule, value is a JSON blob containing all conformers:

```text
Key: "InChI=1/CH4/..."
Value: [{"xyz": "3\n...\nC 0 0 0..."}, {"xyz": "3\n...\nC 0 0 0..."}, ...]
```

**Multi-key** (current) — separate keys for metadata and each conformer:

```text
Key: "InChI=1/CH4/...::meta"       → {"count": 3}
Key: "InChI=1/CH4/...::conf_000000" → xyz_string_0
Key: "InChI=1/CH4/...::conf_000001" → xyz_string_1
Key: "InChI=1/CH4/...::conf_000002" → xyz_string_2
```

### Why Multi-Key Wins

The deciding factor is **streaming writes**. In a preprocessing pipeline, conformers
of the same molecule arrive incrementally over time. With `on_conflict="merge"`, each
new conformer must be appended to the existing set.

| Operation | Single-Key | Multi-Key |
| --- | --- | --- |
| Append 1 conformer (merge) | Read N → concat → **write all N+1** | Write 1 new key + update meta |
| Append 50 conformers | O(n²): ~2500 conformers-worth of I/O | O(n): ~50 conformers-worth + tiny meta updates |
| Read all conformers | 1 b-tree lookup | 1 b-tree lookup + N lookups |

Under single-key, each merge is a read-modify-write of the full value. A molecule
with 50 conformers at 5 KB each means 250 KB of re-serialization and re-write for
every single new conformer — the same 250 KB gets rewritten 50 times.

Under multi-key, each merge only touches a single new key plus a ~20-byte meta
update. Existing conformer keys are never touched again.

### What About Retrieval Speed and Storage?

The difference is negligible in practice:

- **Retrieval**: single-key does one memcpy of 250 KB; multi-key does 51 b-tree
  traversals. Both complete in tens of microseconds — far less than the subsequent
  parsing of XYZ content in the application layer.
- **Storage**: multi-key has ~24 bytes of extra overhead per key (b-tree node
  headers). Overhead is dwarfed by XYZ content which is hundreds of bytes to
  kilobytes per conformer.

### What About Random Conformer Access?

Multi-key technically enables reading a single conformer without loading others.
This capability exists but is **not exposed in the API** because there is no use
case for it. The natural access pattern is always "give me all conformers for
this InChI."

The multi-key design is **not** justified by random access. It is justified
entirely by streaming write efficiency.

## Why Not SQL?

The data model is `InChI → list of XYZ strings` — pure key-value. Using SQL
(SQLite) adds a query parser and b-tree schema layer for zero benefit in the
current access pattern. The SQLite backend exists primarily for environments
where LMDB's system dependency (`liblmdb`) is unavailable.

## Fixed-H InChI as Key

Standard InChI (`InChI=1S/...`) deliberately ignores tautomeric hydrogen
positions, treating tautomers as the same molecule. This is correct for
chemical identity searching but wrong for a structure database — storing
two different 3D geometries under the same key would lose data.

Non-standard Fixed-H InChI (`InChI=1/.../f/h...`) specifies exact hydrogen
positions, giving each tautomer a distinct key. This is the correct level of
specificity for a conformer store.
