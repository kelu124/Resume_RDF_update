"""
resume_rdf.reconcile
====================
Cross-TTL entity reconciliation: find projects and employer/client nodes that
describe the same real-world thing across multiple Turtle files, then rewrite
them to share a single canonical IRI so the graphs can be joined via SPARQL.

Algorithm
---------
1. Parse every TTL file with rdflib.
2. Extract *Project* nodes (labelled by ``cvx:projectName``) and *Company*
   nodes (labelled by ``cv:Name``) from each file.
3. For every cross-file pair of the same entity type, compute a string
   similarity score with :mod:`difflib`.
4. Surface pairs whose score meets *threshold* to the user one by one.
5. On confirmation, record ``old_iri → canonical_iri`` in a mapping (the IRI
   from the file listed **first** on the command line is kept as canonical).
6. Rewrite all TTL files: replace every occurrence of a retired IRI with its
   canonical counterpart, then re-serialise with rdflib.

Requires
--------
``rdflib >= 6.0``  (``pip install rdflib`` or ``pip install "resume-rdf[validate]"``)

CLI usage
---------
::

    cv-reconcile file1.ttl file2.ttl file3.ttl
    cv-reconcile *.ttl --threshold 0.80
    cv-reconcile file1.ttl file2.ttl --dry-run
    cv-reconcile file1.ttl file2.ttl --yes   # accept all matches

Library usage
-------------
::

    from resume_rdf.reconcile import reconcile_interactive
    from pathlib import Path

    n = reconcile_interactive(
        [Path("alice.ttl"), Path("bob.ttl")],
        threshold=0.75,
    )
    print(f"{n} merge(s) applied")
"""

import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

try:
    from rdflib import Graph, Namespace, URIRef
    from rdflib.term import Literal
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "resume_rdf.reconcile requires rdflib.\n"
        "Install it with:  pip install rdflib\n"
        "or:               pip install \"resume-rdf[validate]\""
    ) from _e

_CV  = Namespace("http://purl.org/captsolo/resume-rdf/0.2/cv#")
_CVX = Namespace("http://example.org/cv-extension#")

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Entity:
    """An RDF entity extracted from a Turtle file.

    Attributes:
        iri:    The subject IRI of the entity in its source graph.
        label:  Human-readable label used for similarity comparison.
        kind:   ``"project"`` or ``"company"``.
        source: Path to the TTL file this entity came from.
    """
    iri:    URIRef
    label:  str
    kind:   str
    source: Path


@dataclass(frozen=True)
class Match:
    """A candidate duplicate pair surfaced by :func:`find_matches`.

    Attributes:
        a:     Entity from the earlier file (kept as canonical on merge).
        b:     Entity from the later file (IRI replaced on merge).
        score: Normalised similarity in ``[0, 1]``.
    """
    a:     Entity
    b:     Entity
    score: float


# ─────────────────────────────────────────────────────────────────────────────
# Core logic
# ─────────────────────────────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    """Return a normalised similarity score in ``[0, 1]`` for two strings.

    Uses :class:`difflib.SequenceMatcher` after case-folding, which handles
    small edits, reorderings, and common abbreviations reasonably well without
    any third-party dependencies.

    Args:
        a: First string.
        b: Second string.

    Returns:
        A float in ``[0.0, 1.0]`` where 1.0 means identical.
    """
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def load_entities(ttl_files: list[Path]) -> list[Entity]:
    """Parse TTL files and extract labelled Project and Company entities.

    Extracted node types:

    - ``cvx:Project`` — labelled by ``cvx:projectName``
    - ``cv:Company``  — labelled by ``cv:Name``

    Args:
        ttl_files: Ordered list of Turtle file paths.  The order matters:
            when two entities are merged the one from the earlier file is
            kept as canonical.

    Returns:
        Flat list of :class:`Entity` objects, one per labelled node per file.

    Raises:
        rdflib.exceptions.ParserError: If a file contains invalid Turtle.
    """
    entities: list[Entity] = []
    for path in ttl_files:
        g = Graph()
        g.parse(str(path), format="turtle")

        for iri, _, name in g.triples((None, _CVX.projectName, None)):
            if isinstance(iri, URIRef):
                entities.append(Entity(iri=iri, label=str(name), kind="project", source=path))

        for iri, _, name in g.triples((None, _CV.Name, None)):
            if isinstance(iri, URIRef):
                entities.append(Entity(iri=iri, label=str(name), kind="company", source=path))

    return entities


def find_matches(entities: list[Entity], threshold: float = 0.75) -> list[Match]:
    """Find cross-file entity pairs whose labels are similar enough to be candidates.

    Pairs where both entities come from the same file, or share an identical
    IRI, are skipped.  Only pairs of the same ``kind`` are compared.

    Args:
        entities: List of entities returned by :func:`load_entities`.
        threshold: Minimum similarity score to include a pair.
            ``0.75`` is a good default; lower it to catch more candidates,
            raise it to reduce false positives.

    Returns:
        List of :class:`Match` objects sorted by score descending.
    """
    by_kind: dict[str, list[Entity]] = {}
    for e in entities:
        by_kind.setdefault(e.kind, []).append(e)

    matches: list[Match] = []
    for kind_group in by_kind.values():
        for i, a in enumerate(kind_group):
            for b in kind_group[i + 1:]:
                if a.source == b.source:
                    continue
                if a.iri == b.iri:
                    continue
                score = _similarity(a.label, b.label)
                if score >= threshold:
                    # keep the entity from the earlier file as `a`
                    if a.source > b.source:
                        a, b = b, a
                    matches.append(Match(a=a, b=b, score=score))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def apply_mapping(ttl_files: list[Path], mapping: dict[URIRef, URIRef]) -> dict[Path, int]:
    """Rewrite TTL files using the confirmed ``old_iri → canonical_iri`` mapping.

    For each file, triples whose subject or object IRI appears in *mapping*
    are replaced in-place.  The file is only re-serialised if at least one
    replacement was made.

    Args:
        ttl_files: Paths to rewrite (all files passed to the reconciler).
        mapping:   Dict mapping retired IRIs to their canonical replacements.

    Returns:
        Dict ``{path: n_triples_rewritten}`` for every file that changed.
    """
    results: dict[Path, int] = {}
    for path in ttl_files:
        g = Graph()
        g.parse(str(path), format="turtle")

        n_replaced = 0
        for old_iri, canonical_iri in mapping.items():
            affected = [
                (s, p, o) for s, p, o in g
                if s == old_iri or (isinstance(o, URIRef) and o == old_iri)
            ]
            if not affected:
                continue
            n_replaced += len(affected)
            for s, p, o in affected:
                g.remove((s, p, o))
                new_s = canonical_iri if s == old_iri else s
                new_o = canonical_iri if isinstance(o, URIRef) and o == old_iri else o
                g.add((new_s, p, new_o))

        if n_replaced > 0:
            g.serialize(destination=str(path), format="turtle")
            results[path] = n_replaced

    return results


def reconcile_interactive(
    ttl_files: list[Path],
    threshold: float = 0.75,
    dry_run: bool = False,
    auto_yes: bool = False,
) -> int:
    """Run interactive entity reconciliation across a set of Turtle files.

    Presents each candidate duplicate pair to the user on the terminal and
    collects a yes/no/quit response.  Confirmed merges are accumulated into a
    mapping, then applied to all files in one pass at the end.

    The IRI from the **first file listed** (by argument order) is kept as the
    canonical IRI; the other is replaced everywhere.  Re-order the file
    arguments to control which IRI wins.

    Args:
        ttl_files:  Ordered list of Turtle file paths to reconcile.
        threshold:  Minimum similarity score (``0``–``1``) to surface a pair.
                    Defaults to ``0.75``.
        dry_run:    If ``True``, report what would be done but don't write any
                    files.  Defaults to ``False``.
        auto_yes:   If ``True``, confirm all matches above *threshold*
                    automatically (non-interactive batch mode).
                    Defaults to ``False``.

    Returns:
        Number of merges confirmed (and applied, unless *dry_run* is set).

    Example::

        from pathlib import Path
        from resume_rdf.reconcile import reconcile_interactive

        n = reconcile_interactive(
            [Path("alice.ttl"), Path("bob.ttl")],
            threshold=0.80,
        )
    """
    if not ttl_files:
        print("No TTL files provided.")
        return 0

    print(f"Loading {len(ttl_files)} file(s)…")
    entities = load_entities(ttl_files)
    print(f"  Extracted {len(entities)} entities "
          f"({sum(1 for e in entities if e.kind == 'project')} projects, "
          f"{sum(1 for e in entities if e.kind == 'company')} companies).")

    matches = find_matches(entities, threshold=threshold)
    if not matches:
        print(f"No candidate duplicates found (threshold={threshold:.0%}).")
        return 0

    print(f"\nFound {len(matches)} candidate pair(s) at ≥{threshold:.0%} similarity:\n")

    # IRI → canonical IRI; built up as user confirms matches
    mapping: dict[URIRef, URIRef] = {}
    confirmed = 0

    for idx, match in enumerate(matches, 1):
        a, b = match.a, match.b

        # Resolve through any already-confirmed merges
        canon_a = mapping.get(a.iri, a.iri)
        canon_b = mapping.get(b.iri, b.iri)
        if canon_a == canon_b:
            continue  # already unified by a prior merge

        print(f"── [{idx}/{len(matches)}]  {match.kind.upper()}  "
              f"(similarity {match.score:.0%}) ──")
        print(f"  A: {a.label!r:<45} {a.iri}")
        print(f"     ({a.source.name})")
        print(f"  B: {b.label!r:<45} {b.iri}")
        print(f"     ({b.source.name})")
        print(f"  Canonical if merged → A  ({canon_a})")

        if auto_yes:
            answer = "y"
            print("  [auto-yes]")
        else:
            try:
                answer = input("  Same entity? [y/n/q(uit)] ").strip().lower()
            except EOFError:
                answer = "n"

        if answer.startswith("q"):
            print("Aborted.")
            break

        if answer == "y":
            mapping[canon_b] = canon_a
            confirmed += 1
            print(f"  ✓ Will rewrite  {canon_b}  →  {canon_a}")
        print()

    if confirmed == 0:
        print("No merges confirmed.")
        return 0

    if dry_run:
        print(f"Dry run: {confirmed} merge(s) identified, no files written.")
        return confirmed

    print(f"Applying {confirmed} merge(s) across {len(ttl_files)} file(s)…")
    results = apply_mapping(ttl_files, mapping)
    if results:
        for path, count in sorted(results.items()):
            print(f"  {path.name}: {count} triple(s) rewritten")
    else:
        print("  No triples needed rewriting (entities may only appear in one file).")
    print("Done.")
    return confirmed


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-reconcile``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).  Useful for
            testing without spawning a subprocess.
    """
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
        prog="cv-reconcile",
        description="Reconcile entities across multiple Turtle RDF CV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              cv-reconcile alice.ttl bob.ttl
              cv-reconcile *.ttl --threshold 0.80
              cv-reconcile alice.ttl bob.ttl --dry-run
              cv-reconcile alice.ttl bob.ttl --yes

            Notes
            -----
            The IRI from the first file listed is kept as canonical when two
            entities are merged.  Re-order the arguments to choose which IRI wins.

            Requires rdflib:  pip install rdflib
        """),
    )
    parser.add_argument(
        "ttl_files",
        nargs="+",
        metavar="FILE.ttl",
        help="Two or more Turtle RDF files to reconcile.",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.75,
        metavar="SCORE",
        help="Minimum similarity score to surface a pair (default: 0.75).",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show matches but do not rewrite any files.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Accept all matches above threshold automatically.",
    )

    args = parser.parse_args(argv)
    paths = [Path(p) for p in args.ttl_files]

    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    if len(paths) < 2:
        print("Error: provide at least two TTL files to compare.", file=sys.stderr)
        sys.exit(1)

    reconcile_interactive(
        paths,
        threshold=args.threshold,
        dry_run=args.dry_run,
        auto_yes=args.yes,
    )


if __name__ == "__main__":
    main()
