"""
resume_rdf.api
==============
Core Anthropic API integration: two public entry-points for generating a
Turtle RDF graph from a CV, with transparent file-based caching.
"""

import anthropic

from resume_rdf import cache, ontology, parsing

DEFAULT_MODEL: str = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS: int = 60_000


def generate_graph_from_file(
    file_path: str,
    api_key: str,
    extra_context: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    verbose: bool = True,
) -> tuple[str, dict]:
    """Parse a CV file into a Turtle RDF knowledge graph.

    Checks the local file cache before calling the Anthropic API.  On a cache
    miss the response is stored so subsequent calls with the same inputs return
    instantly without consuming tokens.

    Args:
        file_path: Path to the CV file (``.pdf``, ``.txt``, or ``.md``).
        api_key: Anthropic API key (``sk-ant-...``).
        extra_context: Optional hint for the parser, e.g. preferred output
            language or main industry sectors.
        model: Anthropic model identifier.  Defaults to ``claude-sonnet-4-6``.
        max_tokens: Maximum output tokens.  Defaults to 60 000.
        verbose: When ``True``, print progress dots and a cache-hit notice.

    Returns:
        A ``(turtle_text, usage)`` tuple where *usage* is
        ``{"input_tokens": N, "output_tokens": N}``.

    Example::

        turtle, usage = generate_graph_from_file(
            "my_cv.pdf",
            api_key="sk-ant-...",
            extra_context="Energy sector, English output.",
        )
    """
    content = parsing.build_user_content_from_path(file_path, extra_context)
    key = cache.cache_key(ontology.SYSTEM_PROMPT, model, content)

    hit = cache.load(key)
    if hit is not None:
        if verbose:
            print(f"Cache hit ({key[:12]}…) — skipping API call.")
        return hit

    client = anthropic.Anthropic(api_key=api_key)

    if verbose:
        print("Calling Anthropic API (streaming)...", end=" ", flush=True)

    raw_parts: list[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=ontology.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for chunk in stream.text_stream:
            raw_parts.append(chunk)
            if verbose:
                print(".", end="", flush=True)
        final = stream.get_final_message()

    if verbose:
        print(" done.")

    turtle = parsing.strip_fences("".join(raw_parts))
    usage = {
        "input_tokens":  final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
    }
    cache.save(key, turtle, usage)
    return turtle, usage


def generate_graph_from_bytes(
    file_bytes: bytes,
    file_name: str,
    api_key: str,
    extra_context: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[str, dict]:
    """Parse a CV from raw bytes into a Turtle RDF knowledge graph.

    Suitable for web applications where the file is already in memory
    (e.g. a Streamlit ``UploadedFile``).

    Args:
        file_bytes: Raw file contents.
        file_name: Original filename (used to detect PDF vs. plain text).
        api_key: Anthropic API key (``sk-ant-...``).
        extra_context: Optional hint for the parser.
        model: Anthropic model identifier.  Defaults to ``claude-sonnet-4-6``.
        max_tokens: Maximum output tokens.  Defaults to 60 000.

    Returns:
        A ``(turtle_text, usage)`` tuple where *usage* is
        ``{"input_tokens": N, "output_tokens": N}``.

    Example::

        with open("my_cv.pdf", "rb") as f:
            turtle, usage = generate_graph_from_bytes(
                f.read(), "my_cv.pdf", api_key="sk-ant-..."
            )
    """
    content = parsing.build_user_content_from_bytes(file_bytes, file_name, extra_context)
    key = cache.cache_key(ontology.SYSTEM_PROMPT, model, content)

    hit = cache.load(key)
    if hit is not None:
        return hit

    client = anthropic.Anthropic(api_key=api_key)

    raw_parts: list[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=ontology.SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for chunk in stream.text_stream:
            raw_parts.append(chunk)
        final = stream.get_final_message()

    turtle = parsing.strip_fences("".join(raw_parts))
    usage = {
        "input_tokens":  final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
    }
    cache.save(key, turtle, usage)
    return turtle, usage
