"""
resume_rdf.data
===============
Utilities for downloading and loading the bundled resume dataset.

The dataset is **datasetmaster/resumes** on Hugging Face (MIT licence):
1 866 real and synthetic résumés in JSONL format, each record normalised to
a common schema with fields ``personal_info``, ``experience``, ``education``,
``skills``, ``projects``, ``certifications``, ``languages``, and ``metadata``.

Typical use::

    from resume_rdf.data import download_dataset, load_records

    path = download_dataset()          # downloads once, skips if already present
    records = load_records()           # returns list[dict]
    print(records[0]["personal_info"]) # {"name": ..., "email": ..., ...}
"""

import json
import urllib.request
from pathlib import Path
from typing import Iterator

DATASET_REPO: str = "datasetmaster/resumes"
DATASET_FILE: str = "master_resumes.jsonl"
DATASET_URL: str = (
    "https://huggingface.co/datasets/datasetmaster/resumes"
    "/resolve/main/master_resumes.jsonl"
)

# Default destination: <repo_root>/data/master_resumes.jsonl
_DEFAULT_DATA_DIR: Path = Path(__file__).parent.parent / "data"


def download_dataset(
    dest_dir: str | Path = _DEFAULT_DATA_DIR,
    *,
    force: bool = False,
    verbose: bool = True,
) -> Path:
    """Download ``master_resumes.jsonl`` from Hugging Face into *dest_dir*.

    Tries the ``datasets`` library first (uses the HF cache, respects
    ``HF_HOME``); falls back to a direct HTTP download with ``urllib`` if
    ``datasets`` is not installed.

    Args:
        dest_dir: Directory to save the file.  Created automatically if it
            does not exist.  Defaults to ``<repo_root>/data/``.
        force: Re-download even if the file already exists.  Defaults to
            ``False``.
        verbose: Print progress messages.  Defaults to ``True``.

    Returns:
        :class:`pathlib.Path` pointing to the downloaded file.

    Raises:
        urllib.error.URLError: If the direct HTTP download fails.
        OSError: If *dest_dir* cannot be created or written to.

    Example::

        from resume_rdf.data import download_dataset

        path = download_dataset()
        print(path)  # /path/to/repo/data/master_resumes.jsonl
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_file = dest_dir / DATASET_FILE

    if out_file.exists() and not force:
        if verbose:
            print(f"Already present: {out_file}  ({out_file.stat().st_size / 1_048_576:.1f} MB)")
        return out_file

    try:
        return _download_via_datasets_lib(out_file, verbose=verbose)
    except ImportError:
        if verbose:
            print("`datasets` not installed — falling back to direct HTTP download.")
        return _download_direct(out_file, verbose=verbose)


def _download_via_datasets_lib(out_file: Path, *, verbose: bool) -> Path:
    """Download using the ``datasets`` library (caches to ``~/.cache/huggingface``)."""
    from datasets import load_dataset as _load  # type: ignore

    if verbose:
        print(f"Loading via `datasets` library → {DATASET_REPO} …")
    ds = _load(DATASET_REPO, split="train")
    ds.to_json(str(out_file))
    if verbose:
        print(f"Saved {len(ds):,} records → {out_file}")
    return out_file


def _download_direct(out_file: Path, *, verbose: bool) -> Path:
    """Download the raw JSONL file with ``urllib`` (no extra dependencies)."""
    if verbose:
        print(f"Downloading {DATASET_URL} …")

    def _progress(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            print(
                f"\r  {pct:.1f}%  "
                f"({downloaded / 1_048_576:.1f} / {total_size / 1_048_576:.1f} MB)",
                end="",
                flush=True,
            )

    urllib.request.urlretrieve(DATASET_URL, out_file, reporthook=_progress if verbose else None)
    if verbose:
        print(f"\nSaved → {out_file}  ({out_file.stat().st_size / 1_048_576:.1f} MB)")
    return out_file


def iter_records(
    dest_dir: str | Path = _DEFAULT_DATA_DIR,
    *,
    auto_download: bool = True,
) -> Iterator[dict]:
    """Yield résumé records one at a time from the JSONL file.

    Memory-efficient: reads line-by-line without loading the whole file.

    Args:
        dest_dir: Directory containing ``master_resumes.jsonl``.  Defaults to
            ``<repo_root>/data/``.
        auto_download: If ``True`` and the file is missing, download it first.
            Defaults to ``True``.

    Yields:
        One ``dict`` per résumé record.

    Example::

        from resume_rdf.data import iter_records

        for record in iter_records():
            skills = record.get("skills", [])
            print(record["personal_info"]["name"], "—", skills)
    """
    path = Path(dest_dir) / DATASET_FILE
    if not path.exists():
        if auto_download:
            download_dataset(dest_dir)
        else:
            raise FileNotFoundError(
                f"{path} not found. Run download_dataset() first, or pass auto_download=True."
            )
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_records(
    dest_dir: str | Path = _DEFAULT_DATA_DIR,
    *,
    auto_download: bool = True,
) -> list[dict]:
    """Load all résumé records into a list.

    For large-scale processing prefer :func:`iter_records` to avoid loading
    the entire file into memory at once.

    Args:
        dest_dir: Directory containing ``master_resumes.jsonl``.
        auto_download: Download the file if missing.  Defaults to ``True``.

    Returns:
        List of résumé record dicts.

    Example::

        from resume_rdf.data import load_records

        records = load_records()
        print(len(records))          # 1866
        print(records[0].keys())     # dict_keys(['personal_info', 'experience', ...])
    """
    return list(iter_records(dest_dir, auto_download=auto_download))
