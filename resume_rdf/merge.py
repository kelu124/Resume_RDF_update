"""
resume_rdf.merge
================
Consolidate multiple Turtle CV files of the **same person** into one
enriched, deduplicated TTL.

Typical use-case: Sam Gamgee has two CVs (chronological framing and ESG
framing).  Each TTL captures different descriptions for the same projects.
This module:

1. Reconciles entity IRIs across files (reuses reconcile.py with a
   lowered similarity threshold, since same-person CVs use more varied
   wording than cross-person ones).
2. Loads all reconciled triples into a single graph.
3. For each (subject, predicate) pair with multiple literal values,
   applies a conflict-resolution strategy (see *strategy* parameter).
4. Serialises to the output path.

Strategy options
----------------
``"longest"`` (default)
    Keep the longest string for description/title fields.  Fast, no API
    calls, but silently discards unique information from shorter versions.

``"concat"``
    Concatenate all unique description strings with ``" | "`` as
    separator, longest first.  Zero information loss; output may be
    verbose / slightly redundant.

``"llm"``
    Call the Anthropic Claude API to synthesise a single coherent,
    non-redundant description from all conflicting values.  Results are
    cached (same SHA-256 cache as the CV parser) so repeated runs are
    free.  Requires ``anthropic`` (base dependency) and an API key.

For ``startDate`` / ``endDate`` and other non-descriptive predicates,
the built-in date heuristics are always applied regardless of strategy
(earliest startDate, latest endDate, ``"present"`` beats all dates).
URI-valued objects are always kept as a union across all files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal as TypingLiteral

from rdflib import Graph, Literal, URIRef

from resume_rdf.reconcile import apply_mapping, find_matches, load_entities

# ---------------------------------------------------------------------------
# Predicate buckets
# ---------------------------------------------------------------------------

_CV  = "http://purl.org/captsolo/resume-rdf/0.2/cv#"
_CVX = "http://example.org/cv-extension#"

# String fields where the chosen strategy (longest / concat / llm) applies
_DESCRIPTION_PREDS = frozenset({
    f"{_CVX}projectDescription",
    f"{_CVX}benefitsDelivered",
    f"{_CVX}activitiesPerformed",
    f"{_CVX}roleTitle",
    f"{_CVX}projectName",
    f"{_CV}jobDescription",
    f"{_CV}jobTitle",
    f"{_CV}Name",
    "http://xmlns.com/foaf/0.1/name",
    "http://www.w3.org/2000/01/rdf-schema#label",
})

_PREFER_EARLIEST = frozenset({
    f"{_CV}startDate",
    f"{_CVX}startDate",
})

_PREFER_LATEST = frozenset({
    f"{_CV}endDate",
    f"{_CVX}endDate",
})

# Default model for LLM synthesis (cheapest/fastest Claude)
_MERGE_MODEL = "claude-haiku-4-5-20251001"

_MERGE_SYSTEM = (
    "You are a professional CV editor. "
    "Given multiple descriptions of the same work experience or project "
    "written by the same person for different audiences, produce one clear, "
    "concise, non-redundant description that captures all unique information. "
    "Return only the synthesized description — no preamble, no commentary, "
    "no bullet points unless the originals used them."
)

# ---------------------------------------------------------------------------
# Public return type
# ---------------------------------------------------------------------------

@dataclass
class MergeStats:
    """Statistics returned by :func:`consolidate_ttls`."""
    input_files: int
    input_triples: int
    iri_mappings: int
    conflicts_resolved: int
    output_triples: int
    llm_calls: int = field(default=0)
    llm_cache_hits: int = field(default=0)
    dedup_removed: int = field(default=0)


# ---------------------------------------------------------------------------
# Cache helpers (text, not Turtle)
# ---------------------------------------------------------------------------

def _text_cache_dir() -> Path:
    d = Path(os.environ.get("LLM_CACHE_DIR", Path(__file__).parent.parent / "cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _text_cache_key(pred: str, values: list[str], model: str) -> str:
    payload = json.dumps(
        {"predicate": pred, "values": sorted(values), "model": model},
        sort_keys=True, ensure_ascii=False,
    ).encode()
    return "merge_" + hashlib.sha256(payload).hexdigest()


def _text_cache_load(key: str) -> str | None:
    path = _text_cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["text"]


def _text_cache_save(key: str, text: str, usage: dict) -> None:
    path = _text_cache_dir() / f"{key}.json"
    path.write_text(
        json.dumps({"text": text, "usage": usage}, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Per-strategy literal resolvers
# ---------------------------------------------------------------------------

def _is_present(val: str) -> bool:
    return val.strip().lower() in {"present", "current", "now", "ongoing"}


def _pick_date(pred: URIRef, values: list[Literal]) -> Literal:
    pred_str = str(pred)
    if pred_str in _PREFER_EARLIEST:
        dated = [v for v in values if not _is_present(str(v))]
        return min(dated, key=lambda v: str(v)) if dated else values[0]
    # PREFER_LATEST
    present = [v for v in values if _is_present(str(v))]
    if present:
        return present[0]
    return max(values, key=lambda v: str(v))


def _pick_longest(values: list[Literal]) -> Literal:
    return max(values, key=lambda v: len(str(v)))


def _concat(values: list[Literal]) -> Literal:
    """Join all unique strings longest-first, separated by `` | ``."""
    seen: set[str] = set()
    parts: list[str] = []
    for v in sorted(values, key=lambda x: len(str(x)), reverse=True):
        s = str(v).strip()
        if s and s not in seen:
            seen.add(s)
            parts.append(s)
    return Literal(" | ".join(parts))


def _llm_synthesize(
    pred: URIRef,
    values: list[Literal],
    api_key: str,
    model: str,
    stats: MergeStats,
) -> Literal:
    """Call Claude to synthesize conflicting descriptions; use cache when possible."""
    import anthropic  # imported lazily — only needed for llm strategy

    str_values = [str(v) for v in values]
    key = _text_cache_key(str(pred), str_values, model)

    cached = _text_cache_load(key)
    if cached is not None:
        stats.llm_cache_hits += 1
        return Literal(cached)

    descriptions = "\n\n".join(
        f"Version {i + 1}:\n{v}" for i, v in enumerate(str_values)
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_MERGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Synthesize these descriptions into one:\n\n{descriptions}",
        }],
    )
    text = response.content[0].text.strip()
    _text_cache_save(key, text, {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    })
    stats.llm_calls += 1
    return Literal(text)


def _resolve_literals(
    pred: URIRef,
    values: list[Literal],
    strategy: str,
    api_key: str | None,
    model: str,
    stats: MergeStats,
) -> Literal:
    """Apply the right resolution rule for *pred* under *strategy*."""
    pred_str = str(pred)

    # Date predicates: always use built-in heuristic regardless of strategy
    if pred_str in _PREFER_EARLIEST or pred_str in _PREFER_LATEST:
        return _pick_date(pred, values)

    # Non-description predicates: longest wins regardless of strategy
    if pred_str not in _DESCRIPTION_PREDS:
        return _pick_longest(values)

    # Description predicates: apply chosen strategy
    if strategy == "longest":
        return _pick_longest(values)
    if strategy == "concat":
        return _concat(values)
    if strategy == "llm":
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                'strategy="llm" requires an api_key argument or ANTHROPIC_API_KEY env var'
            )
        return _llm_synthesize(pred, values, api_key, model, stats)
    raise ValueError(f"Unknown strategy {strategy!r}; choose 'longest', 'concat', or 'llm'")


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _replace_iri_references(g: Graph, old: URIRef, new: URIRef) -> None:
    for s, p, _ in list(g.triples((None, None, old))):
        g.remove((s, p, old))
        g.add((s, p, new))


def _remove_node(g: Graph, node: URIRef) -> None:
    for triple in list(g.triples((node, None, None))):
        g.remove(triple)


def _merge_node(g: Graph, winner: URIRef, loser: URIRef) -> None:
    """Copy any property from *loser* that *winner* lacks, then delete *loser*."""
    for _, p, o in list(g.triples((loser, None, None))):
        if not list(g.triples((winner, p, None))):
            g.add((winner, p, o))
    _replace_iri_references(g, loser, winner)
    _remove_node(g, loser)


_SKILL_LEVEL_RANK: dict[str, int] = {
    "expert": 5,
    "advanced": 4,
    "skilled": 3,
    "proficient": 3,
    "intermediate": 2,
    "beginner": 1,
    "basic": 1,
}

_RDF_TYPE      = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_SKILL_NAME    = URIRef(f"{_CV}skillName")
_SKILL_LVL     = URIRef(f"{_CV}skillLevel")
_SKILL_YRS     = URIRef(f"{_CV}skillYearsExperience")
_BIBO_ARTICLE  = URIRef("http://purl.org/ontology/bibo/Article")
_BIBO_DOI      = URIRef("http://purl.org/ontology/bibo/doi")
_DCT_TITLE     = URIRef("http://purl.org/dc/terms/title")
_CV_EDUCATION  = URIRef(f"{_CV}Education")
_CV_DEGREE     = URIRef(f"{_CV}degreeType")
_CV_MAJOR      = URIRef(f"{_CV}eduMajor")
_CV_INST       = URIRef(f"{_CV}studiedIn")
_CVX_TRAINING  = URIRef(f"{_CVX}Training")
_CVX_TRAIN_TTL = URIRef(f"{_CVX}trainingTitle")
_CVX_PROV      = URIRef(f"{_CVX}trainingProvider")
_CVX_TRAIN_DT  = URIRef(f"{_CVX}trainingDate")
_CVX_CERT      = URIRef(f"{_CVX}certificationName")


def _first_literal(g: Graph, subj: URIRef, pred: URIRef) -> str:
    for _, _, o in g.triples((subj, pred, None)):
        if isinstance(o, Literal):
            return str(o).strip()
    return ""


def _first_str(g: Graph, subj: URIRef, pred: URIRef) -> str:
    """Return string representation of the first object (literal or IRI)."""
    for _, _, o in g.triples((subj, pred, None)):
        return str(o).strip()
    return ""


def _first_int(g: Graph, subj: URIRef, pred: URIRef) -> int:
    val = _first_literal(g, subj, pred)
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _triple_count(g: Graph, subj: URIRef) -> int:
    return sum(1 for _ in g.triples((subj, None, None)))


def _dedup_skills(g: Graph) -> int:
    """Deduplicate near-identical skill nodes; return count removed."""
    skills = [s for s, _, _ in g.triples((None, _SKILL_NAME, None)) if isinstance(s, URIRef)]
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(skills):
        if node_a in merged_away:
            continue
        name_a = _first_literal(g, node_a, _SKILL_NAME)
        for node_b in skills[i + 1:]:
            if node_b in merged_away:
                continue
            name_b = _first_literal(g, node_b, _SKILL_NAME)
            if _similarity(name_a, name_b) < 0.82:
                continue
            rank_a = _SKILL_LEVEL_RANK.get(_first_literal(g, node_a, _SKILL_LVL).lower(), 0)
            rank_b = _SKILL_LEVEL_RANK.get(_first_literal(g, node_b, _SKILL_LVL).lower(), 0)
            yrs_a = _first_int(g, node_a, _SKILL_YRS)
            yrs_b = _first_int(g, node_b, _SKILL_YRS)
            a_wins = (
                rank_a > rank_b
                or (rank_a == rank_b and yrs_a > yrs_b)
                or (rank_a == rank_b and yrs_a == yrs_b and len(name_a) >= len(name_b))
            )
            winner, loser = (node_a, node_b) if a_wins else (node_b, node_a)
            _merge_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def _dedup_publications(g: Graph) -> int:
    """Deduplicate publication nodes by DOI (exact) or title similarity; return count removed."""
    pubs: list[URIRef] = [s for s, _, _ in g.triples((None, _RDF_TYPE, _BIBO_ARTICLE))
                          if isinstance(s, URIRef)]
    # Also catch publication-like nodes that have dcterms:title but no rdf:type bibo:Article
    for s, _, _ in g.triples((None, _DCT_TITLE, None)):
        if isinstance(s, URIRef) and s not in pubs:
            pubs.append(s)
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(pubs):
        if node_a in merged_away:
            continue
        doi_a   = _first_literal(g, node_a, _BIBO_DOI).lower()
        title_a = _first_literal(g, node_a, _DCT_TITLE)
        for node_b in pubs[i + 1:]:
            if node_b in merged_away:
                continue
            doi_b   = _first_literal(g, node_b, _BIBO_DOI).lower()
            title_b = _first_literal(g, node_b, _DCT_TITLE)
            doi_match   = bool(doi_a and doi_b and doi_a == doi_b)
            title_match = bool(title_a and title_b and _similarity(title_a, title_b) >= 0.88)
            if not (doi_match or title_match):
                continue
            winner, loser = (
                (node_a, node_b) if _triple_count(g, node_a) >= _triple_count(g, node_b)
                else (node_b, node_a)
            )
            _merge_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def _dedup_education(g: Graph) -> int:
    """Deduplicate education nodes; return count removed."""
    edu_nodes = [s for s, _, _ in g.triples((None, _RDF_TYPE, _CV_EDUCATION))
                 if isinstance(s, URIRef)]
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(edu_nodes):
        if node_a in merged_away:
            continue
        key_a = " ".join([
            _first_literal(g, node_a, _CV_DEGREE),
            _first_literal(g, node_a, _CV_MAJOR),
            _first_str(g, node_a, _CV_INST),
        ]).strip()
        for node_b in edu_nodes[i + 1:]:
            if node_b in merged_away:
                continue
            key_b = " ".join([
                _first_literal(g, node_b, _CV_DEGREE),
                _first_literal(g, node_b, _CV_MAJOR),
                _first_str(g, node_b, _CV_INST),
            ]).strip()
            if not key_a or not key_b or _similarity(key_a, key_b) < 0.85:
                continue
            winner, loser = (
                (node_a, node_b) if _triple_count(g, node_a) >= _triple_count(g, node_b)
                else (node_b, node_a)
            )
            _merge_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def _dedup_training(g: Graph) -> int:
    """Deduplicate training/certification nodes; return count removed."""
    training_nodes = [s for s, _, _ in g.triples((None, _RDF_TYPE, _CVX_TRAINING))
                      if isinstance(s, URIRef)]
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(training_nodes):
        if node_a in merged_away:
            continue
        title_a = _first_literal(g, node_a, _CVX_TRAIN_TTL) or _first_literal(g, node_a, _CVX_CERT)
        key_a = " ".join([
            _first_literal(g, node_a, _CVX_PROV),
            title_a,
            _first_literal(g, node_a, _CVX_TRAIN_DT),
        ]).strip()
        for node_b in training_nodes[i + 1:]:
            if node_b in merged_away:
                continue
            title_b = _first_literal(g, node_b, _CVX_TRAIN_TTL) or _first_literal(g, node_b, _CVX_CERT)
            key_b = " ".join([
                _first_literal(g, node_b, _CVX_PROV),
                title_b,
                _first_literal(g, node_b, _CVX_TRAIN_DT),
            ]).strip()
            if not key_a or not key_b or _similarity(key_a, key_b) < 0.90:
                continue
            winner, loser = (
                (node_a, node_b) if _triple_count(g, node_a) >= _triple_count(g, node_b)
                else (node_b, node_a)
            )
            _merge_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def _dedup_graph(g: Graph) -> int:
    """Run all four deduplication passes; return total duplicate nodes removed."""
    total = 0
    total += _dedup_skills(g)
    total += _dedup_publications(g)
    total += _dedup_education(g)
    total += _dedup_training(g)
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def consolidate_ttls(
    ttl_files: list[str | Path],
    output_file: str | Path,
    *,
    threshold: float = 0.70,
    strategy: TypingLiteral["longest", "concat", "llm"] = "longest",
    api_key: str | None = None,
    model: str = _MERGE_MODEL,
) -> MergeStats:
    """Merge *ttl_files* (same person, different framings) into *output_file*.

    Parameters
    ----------
    ttl_files:
        Two or more Turtle files to merge.
    output_file:
        Destination path for the consolidated TTL.
    threshold:
        Similarity threshold passed to
        :func:`~resume_rdf.reconcile.find_matches`.
        Lower values merge more aggressively; 0.70 works well for
        same-person CVs.
    strategy:
        How to resolve conflicting literal values on description/title
        predicates.

        ``"longest"``
            Keep the longest string (fast, may lose info).
        ``"concat"``
            Concatenate all unique values with ``" | "`` (no loss, verbose).
        ``"llm"``
            Ask Claude to synthesise a single coherent description
            (best quality; uses cache to avoid re-calling the API).
    api_key:
        Anthropic API key — required when *strategy* is ``"llm"``.
        Falls back to the ``ANTHROPIC_API_KEY`` environment variable.
    model:
        Claude model to use for LLM synthesis
        (default: ``claude-haiku-4-5-20251001``).

    Returns
    -------
    MergeStats
        Counts of input/output triples, IRI mappings, resolved conflicts,
        and (for ``"llm"`` strategy) API calls and cache hits.
    """
    ttl_files = [Path(f) for f in ttl_files]
    output_file = Path(output_file)
    stats = MergeStats(
        input_files=len(ttl_files),
        input_triples=0,
        iri_mappings=0,
        conflicts_resolved=0,
        output_triples=0,
    )

    # ------------------------------------------------------------------
    # Step 1: reconcile IRIs in temporary copies
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        tmp_paths = [Path(tmp) / f.name for f in ttl_files]
        for src, dst in zip(ttl_files, tmp_paths):
            shutil.copy(src, dst)

        entities = load_entities(tmp_paths)
        matches = find_matches(entities, threshold=threshold)

        mapping: dict[URIRef, URIRef] = {}
        for m in matches:
            canon_a = mapping.get(m.a.iri, m.a.iri)
            canon_b = mapping.get(m.b.iri, m.b.iri)
            if canon_a == canon_b:
                continue
            idx_a = next(
                (i for i, p in enumerate(tmp_paths) if p == m.a.source), 999
            )
            idx_b = next(
                (i for i, p in enumerate(tmp_paths) if p == m.b.source), 999
            )
            if idx_a <= idx_b:
                mapping[canon_b] = canon_a
            else:
                mapping[canon_a] = canon_b

        if mapping:
            apply_mapping(tmp_paths, mapping)

        stats.iri_mappings = len(mapping)

        per_graph: list[Graph] = []
        for p in tmp_paths:
            g = Graph()
            g.parse(str(p), format="turtle")
            stats.input_triples += len(g)
            per_graph.append(g)

    # ------------------------------------------------------------------
    # Step 2: collect (subject, predicate) → [objects]
    # ------------------------------------------------------------------
    sp_map: dict[tuple, list] = defaultdict(list)
    for g in per_graph:
        for s, p, o in g:
            sp_map[(s, p)].append(o)

    # ------------------------------------------------------------------
    # Step 3: build merged graph
    # ------------------------------------------------------------------
    merged = Graph()
    for prefix, ns in per_graph[0].namespaces():
        merged.bind(prefix, ns)

    for (s, p), objects in sp_map.items():
        # Deduplicate by string value
        seen: dict[str, object] = {}
        for o in objects:
            key = str(o)
            if key not in seen:
                seen[key] = o
        unique = list(seen.values())

        if len(unique) == 1:
            merged.add((s, p, unique[0]))
            continue

        literals = [o for o in unique if isinstance(o, Literal)]
        uris = [o for o in unique if isinstance(o, URIRef)]

        for u in uris:
            merged.add((s, p, u))

        if literals:
            if len(literals) > 1:
                stats.conflicts_resolved += 1
            merged.add((s, p, _resolve_literals(p, literals, strategy, api_key, model, stats)))

    # ------------------------------------------------------------------
    # Step 3b: deduplication
    # ------------------------------------------------------------------
    stats.dedup_removed = _dedup_graph(merged)

    # ------------------------------------------------------------------
    # Step 4: serialise
    # ------------------------------------------------------------------
    output_file.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(output_file), format="turtle")
    stats.output_triples = len(merged)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cv-merge",
        description="Consolidate multiple TTL files of the same person into one enriched TTL.",
    )
    parser.add_argument("files", nargs="+", metavar="FILE.ttl",
                        help="Input Turtle files (≥ 2, same person)")
    parser.add_argument("--output", "-o", required=True, metavar="OUT.ttl",
                        help="Output path for the merged TTL")
    parser.add_argument(
        "--threshold", type=float, default=0.70, metavar="FLOAT",
        help="Entity similarity threshold for reconciliation (default: 0.70)",
    )
    parser.add_argument(
        "--strategy", choices=["longest", "concat", "llm"], default="longest",
        help=(
            "Conflict-resolution strategy for description fields: "
            "'longest' (default) keeps the longest string; "
            "'concat' joins all values with ' | '; "
            "'llm' synthesizes via Claude API (cached)"
        ),
    )
    parser.add_argument(
        "--api-key", metavar="KEY",
        help="Anthropic API key (required for --strategy llm; falls back to ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--model", default=_MERGE_MODEL, metavar="MODEL",
        help=f"Claude model for LLM synthesis (default: {_MERGE_MODEL})",
    )
    args = parser.parse_args(argv)

    if len(args.files) < 2:
        parser.error("At least 2 input files required.")

    stats = consolidate_ttls(
        args.files,
        args.output,
        threshold=args.threshold,
        strategy=args.strategy,
        api_key=args.api_key,
        model=args.model,
    )
    print(f"Merged {stats.input_files} file(s)  ({stats.input_triples} input triples)")
    print(f"  Strategy             : {args.strategy}")
    print(f"  IRI mappings applied : {stats.iri_mappings}")
    print(f"  Conflicts resolved   : {stats.conflicts_resolved}")
    print(f"  Duplicates removed   : {stats.dedup_removed}")
    if args.strategy == "llm":
        print(f"  LLM API calls        : {stats.llm_calls}")
        print(f"  LLM cache hits       : {stats.llm_cache_hits}")
    print(f"  Output triples       : {stats.output_triples}")
    print(f"  Saved to             : {args.output}")
