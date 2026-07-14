"""
Common utilities shared by LMDB and SQLite builder backends.
"""

from typing import Iterator

import pandas as pd

from ..config.config import BuilderSettings

ConformerData = dict
ConflictMode = str


def print_progress(
    elapsed: float,
    processed: int,
    speed: float,
    batch_result: dict,
    batch_time: float,
):
    """Print a progress line for a completed batch."""
    parts = [f"W:{batch_result['written']}", f"O:{batch_result['overwritten']}"]
    if batch_result.get("skipped"):
        parts.append(f"S:{batch_result['skipped']}")
    if batch_result.get("merged"):
        parts.append(f"M:{batch_result['merged']}")
    detail = ",".join(parts)
    print(
        f"[{elapsed:.1f}s] Total {processed} mols, "
        f"Speed: {speed:.1f} mol/s, "
        f"Batch [{detail}] in {batch_time:.2f}s"
    )


def iter_mapping(
    mapping_file: str,
    xyz_path_column: str | None = None,
    inchi_column: str | None = None,
) -> Iterator[tuple[str, list[ConformerData]]]:
    """
    Generator that yields (inchi, conformers) from a CSV mapping file.

    This bridges the file-based workflow to the stream-based builder.
    XYZ content read from files is wrapped as {"xyz": content} dicts.

    Args:
        mapping_file: Path to CSV with xyz_path and inchi columns.
        xyz_path_column: Name of the column containing XYZ file paths.
        inchi_column: Name of the column containing Fixed-H InChI.

    Yields:
        (inchi, [conformer_dict]) tuples
    """
    builder = BuilderSettings()
    if xyz_path_column is None:
        xyz_path_column = builder.xyz_path_column
    if inchi_column is None:
        inchi_column = builder.inchi_column

    df = pd.read_csv(mapping_file)

    if xyz_path_column not in df.columns or inchi_column not in df.columns:
        raise ValueError(
            f"CSV must have '{xyz_path_column}' and '{inchi_column}' columns"
        )

    grouped = df.groupby(inchi_column)[xyz_path_column]

    for inchi, xyz_paths in grouped:
        conformers: list[ConformerData] = []
        for xyz_path in xyz_paths:
            with open(xyz_path, "r") as f:
                conformers.append({"xyz": f.read()})
        if conformers:
            yield (inchi, conformers)
