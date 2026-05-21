"""
llm_cache.py
============
Simple file-based cache for Anthropic API responses.

Cache key  : SHA-256 of (system_prompt + model + serialised user content)
Cache store: cache/<hex>.json  —  {"turtle": "...", "usage": {...}}
Cache dir  : ./cache/ by default; override with LLM_CACHE_DIR env var.

The cache directory is git-ignored. Delete any .json file (or the whole
cache/ folder) to force a fresh API call for that input.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _cache_dir() -> Path:
    d = Path(os.environ.get("LLM_CACHE_DIR", Path(__file__).parent / "cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(system_prompt: str, model: str, user_content: Any) -> str:
    """Return a hex digest that uniquely identifies this (prompt, model, content) triple."""
    payload = json.dumps(
        {"system": system_prompt, "model": model, "content": user_content},
        sort_keys=True,
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load(key: str) -> tuple[str, dict] | None:
    """Return (turtle_text, usage_dict) from cache, or None on a miss."""
    path = _cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["turtle"], data["usage"]


def save(key: str, turtle: str, usage: dict) -> None:
    """Persist an API response to cache."""
    path = _cache_dir() / f"{key}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump({"turtle": turtle, "usage": usage}, f, ensure_ascii=False)
