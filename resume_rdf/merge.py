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
   applies a field-type heuristic:
     - description / title fields  → longest string wins
     - startDate                   → earliest date wins
     - endDate                     → latest date wins ("present" beats all)
     - URI-valued objects           → full set union (no loss)
4. Serialises to the output path.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from resume_rdf.reconcile import apply_mapping, find_matches, load_entities

# ---------------------------------------------------------------------------
# Predicate buckets
# ---------------------------------------------------------------------------

_CV  = "http://purl.org/captsolo/resume-rdf/0.2/cv#"
_CVX = "http://example.org/cv-extension#"

_PREFER_LONGEST = {
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
}

_PREFER_EARLIEST = {
    f"{_CV}startDate",
    f"{_CVX}startDate",
}

_PREFER_LATEST = {
    f"{_CV}endDate",
    f"{_CVX}endDate",
}


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_present(val: str) -> bool:
    return val.strip().lower() in {"present", "current", "now", "ongoing"}


def _pick_literal(pred: URIRef, values: list[Literal]) -> Literal:
    """Choose one literal from a conflict set for *pred*."""
    pred_str = str(pred)

    if pred_str in _PREFER_LONGEST:
        return max(values, key=lambda v: len(str(v)))

    if pred_str in _PREFER_EARLIEST:
        dated = [v for v in values if not _is_present(str(v))]
        if dated:
            return min(dated, key=lambda v: str(v))
        return values[0]

    if pred_str in _PREFER_LATEST:
        present = [v for v in values if _is_present(str(v))]
        if present:
            return present[0]
        return max(values, key=lambda v: str(v))

    # Default fallback: longest
    return max(values, key=lambda v: len(str(v)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def consolidate_ttls(
    ttl_files: list[str | Path],
    output_file: str | Path,
    *,
    threshold: float = 0.70,
) -> MergeStats:
    """Merge *ttl_files* (same person, different framings) into *output_file*.

    Parameters
    ----------
    ttl_files:
        Two or more Turtle files to merge.
    output_file:
        Destination path for the consolidated TTL.
    threshold:
        Similarity threshold passed to :func:`~resume_rdf.reconcile.find_matches`.
        Lower values merge more aggressively; 0.70 works well for same-person CVs.

    Returns
    -------
    MergeStats
        Counts of input/output triples, IRI mappings, and resolved conflicts.
    """
    ttl_files = [Path(f) for f in ttl_files]
    output_file = Path(output_file)

    # ------------------------------------------------------------------
    # Step 1: reconcile IRIs in temporary copies
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        tmp_paths = [Path(tmp) / f.name for f in ttl_files]
        for src, dst in zip(ttl_files, tmp_paths):
            shutil.copy(src, dst)

        entities = load_entities(tmp_paths)
        matches = find_matches(entities, threshold=threshold)

        # Build canonical IRI mapping: prefer the IRI from the earliest file
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

        iri_count = len(mapping)

        # Load reconciled files
        per_graph: list[Graph] = []
        input_count = 0
        for p in tmp_paths:
            g = Graph()
            g.parse(str(p), format="turtle")
            input_count += len(g)
            per_graph.append(g)

    # ------------------------------------------------------------------
    # Step 2: collect (subject, predicate) → [objects]
    # ------------------------------------------------------------------
    sp_map: dict[tuple[URIRef | None, URIRef], list] = defaultdict(list)
    for g in per_graph:
        for s, p, o in g:
            sp_map[(s, p)].append(o)

    # ------------------------------------------------------------------
    # Step 3: build merged graph
    # ------------------------------------------------------------------
    merged = Graph()
    for prefix, ns in per_graph[0].namespaces():
        merged.bind(prefix, ns)

    conflicts_resolved = 0

    for (s, p), objects in sp_map.items():
        # Deduplicate by string value first
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

        # Always keep all URIs (type assertions, skill links, etc.)
        for u in uris:
            merged.add((s, p, u))

        # For literals: pick one by heuristic
        if literals:
            if len(literals) > 1:
                conflicts_resolved += 1
            merged.add((s, p, _pick_literal(p, literals)))

    # ------------------------------------------------------------------
    # Step 4: serialise
    # ------------------------------------------------------------------
    output_file.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(output_file), format="turtle")

    return MergeStats(
        input_files=len(ttl_files),
        input_triples=input_count,
        iri_mappings=iri_count,
        conflicts_resolved=conflicts_resolved,
        output_triples=len(merged),
    )


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
    args = parser.parse_args(argv)

    if len(args.files) < 2:
        parser.error("At least 2 input files required.")

    stats = consolidate_ttls(args.files, args.output, threshold=args.threshold)
    print(f"Merged {stats.input_files} file(s)  ({stats.input_triples} input triples)")
    print(f"  IRI mappings applied : {stats.iri_mappings}")
    print(f"  Conflicts resolved   : {stats.conflicts_resolved}")
    print(f"  Output triples       : {stats.output_triples}")
    print(f"  Saved to             : {args.output}")
