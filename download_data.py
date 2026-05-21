"""
download_data.py
================
Download the master_resumes dataset from Hugging Face into data/.

Usage
-----
  # With the `datasets` library (recommended):
  python download_data.py

  # Or just curl:
  mkdir -p data
  curl -L https://huggingface.co/datasets/datasetmaster/resumes/resolve/main/master_resumes.jsonl \
       -o data/master_resumes.jsonl

Dataset: datasetmaster/resumes
  1 866 records · 6 MB · JSONL · MIT licence
  Fields per record: personal_info, experience, education, skills, projects,
                     certifications, languages, metadata
"""

import os
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATASET_URL = (
    "https://huggingface.co/datasets/datasetmaster/resumes"
    "/resolve/main/master_resumes.jsonl"
)
OUT_FILE = DATA_DIR / "master_resumes.jsonl"


def download_with_datasets() -> None:
    """Download via the `datasets` library (caches to ~/.cache/huggingface)."""
    from datasets import load_dataset  # type: ignore

    print("Loading via `datasets` library …")
    ds = load_dataset("datasetmaster/resumes", split="train")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ds.to_json(str(OUT_FILE))
    print(f"Saved {len(ds):,} records → {OUT_FILE}")


def download_direct() -> None:
    """Download the raw JSONL file with urllib (no extra dependencies)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DATASET_URL} …")

    def _progress(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            print(f"\r  {pct:.1f}%  ({downloaded / 1_048_576:.1f} / {total_size / 1_048_576:.1f} MB)", end="", flush=True)

    urllib.request.urlretrieve(DATASET_URL, OUT_FILE, reporthook=_progress)
    print(f"\nSaved → {OUT_FILE}  ({OUT_FILE.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    if OUT_FILE.exists():
        print(f"Already present: {OUT_FILE}  ({OUT_FILE.stat().st_size / 1_048_576:.1f} MB)")
    else:
        try:
            download_with_datasets()
        except ImportError:
            print("`datasets` not installed — falling back to direct HTTP download.")
            download_direct()
