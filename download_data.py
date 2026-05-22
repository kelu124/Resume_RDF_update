"""
download_data.py  —  CLI helper
================================
Thin wrapper around :func:`resume_rdf.data.download_dataset`.
For programmatic use, import the library directly::

    from resume_rdf import download_dataset, load_records

Run:  python download_data.py
"""

from resume_rdf.data import download_dataset

if __name__ == "__main__":
    download_dataset()
