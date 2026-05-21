"""
resume_rdf.cache
================
File-based cache for Anthropic API responses.

Cache key  : SHA-256 of (system_prompt + model + serialised user content).
Cache store: ``<cache_dir>/<hex>.json``  →  ``{"turtle": "...", "usage": {...}}``.
Cache dir  : ``./cache/`` by default; override with the ``LLM_CACHE_DIR``
             environment variable.

The cache directory is git-ignored.  Delete any ``.json`` file (or the whole
``cache/`` folder) to force a fresh API call for that input.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _cache_dir() -> Path:
    d = Path(os.environ.get("LLM_CACHE_DIR", Path(__file__).parent.parent / "cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(system_prompt: str, model: str, user_content: Any) -> str:
    """Return a hex digest that uniquely identifies this (prompt, model, content) triple.

    Args:
        system_prompt: The full system prompt string.
        model: Anthropic model identifier (e.g. ``"claude-sonnet-4-6"``).
        user_content: The user content block — any JSON-serialisable value.

    Returns:
        64-character lowercase hex string (SHA-256).
    """
    payload = json.dumps(
        {"system": system_prompt, "model": model, "content": user_content},
        sort_keys=True,
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load(key: str) -> tuple[str, dict] | None:
    """Return a cached ``(turtle_text, usage_dict)`` pair, or ``None`` on a miss.

    Args:
        key: Cache key returned by :func:`cache_key`.

    Returns:
        ``(turtle, usage)`` on a hit, ``None`` on a miss.
    """
    path = _cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["turtle"], data["usage"]


def save(key: str, turtle: str, usage: dict) -> None:
    """Persist an API response to the cache.

    Args:
        key: Cache key returned by :func:`cache_key`.
        turtle: Turtle RDF text to store.
        usage: Token-usage dict (``{"input_tokens": N, "output_tokens": N}``).
    """
    path = _cache_dir() / f"{key}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump({"turtle": turtle, "usage": usage}, f, ensure_ascii=False)
