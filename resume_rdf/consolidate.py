"""
resume_rdf.consolidate
======================
``cv-consolidate`` CLI — apply a synonym IRI mapping to a Turtle RDF file.

Synonyms can be supplied via a Turtle file or inline on the command line.

**Synonyms file** (``--synonyms``): a Turtle document containing
``owl:sameAs`` triples.  The *subject* is the old/duplicate IRI; the
*object* is the canonical IRI that replaces it::

    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix : <http://example.org/cv/> .

    :proj_duplicate  owl:sameAs :proj_canonical .
    :company_variant owl:sameAs :company_canonical .

**Inline synonyms** (``--sameas``): the first value is the canonical IRI,
the rest are the duplicates merged into it::

    cv-consolidate cv.ttl --sameas wh_danone_bop_2011 wh_danone_bop_india wh_danone_bop_india_2011

Bare slugs are expanded to ``http://example.org/cv/<slug>``.  Both flags
may be combined in the same invocation.  Every occurrence of a duplicate
IRI — in subject, predicate, or object position — is rewritten.

Usage::

    cv-consolidate graph.ttl --synonyms synonyms.ttl
    cv-consolidate graph.ttl --synonyms synonyms.ttl --output fixed.ttl
    cv-consolidate cv.ttl --sameas canonical dup1 dup2
    cv-consolidate cv.ttl --sameas canonical1 dup1 --sameas canonical2 dup3
"""

import argparse
import sys
import textwrap
from pathlib import Path

_BASE_NS = "http://example.org/cv/"


def _require_rdflib() -> None:
    try:
        import rdflib  # noqa: F401
    except ImportError:
        sys.exit(
            "Error: rdflib is required for cv-consolidate.\n"
            "  pip install rdflib\n"
            "  or: pip install 'resume-rdf[validate]'"
        )


def _resolve_iri(value: str) -> "URIRef":
    """Expand a slug or full IRI string to a URIRef."""
    from rdflib import URIRef
    v = value.strip("<>")
    if v.startswith(("http://", "https://", "urn:")):
        return URIRef(v)
    return URIRef(_BASE_NS + v)


def load_synonym_map(synonyms_path: "str | Path") -> dict:
    """Return ``{old_IRI: canonical_IRI}`` from ``owl:sameAs`` triples."""
    _require_rdflib()
    from rdflib import Graph, OWL, URIRef

    g = Graph()
    g.parse(Path(synonyms_path), format="turtle")
    mapping: dict[URIRef, URIRef] = {}
    for s, _p, o in g.triples((None, OWL.sameAs, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef) and s != o:
            mapping[s] = URIRef(str(o))
    return mapping


def consolidate_synonyms(
    input_file: "str | Path",
    synonyms_file: "str | Path | None" = None,
    output_file: "str | Path | None" = None,
    *,
    extra_mapping: "dict | None" = None,
    verbose: bool = False,
) -> int:
    """Rewrite IRIs in *input_file* according to the combined synonym mapping.

    Sources are merged: *synonyms_file* (``owl:sameAs`` Turtle) and/or
    *extra_mapping* (pre-built ``{old_URIRef: canonical_URIRef}`` dict).

    Returns the number of triples that contained at least one rewritten IRI.
    Output defaults to ``<stem>_consolidated.ttl`` in the same directory.
    """
    _require_rdflib()
    from rdflib import Graph

    input_path = Path(input_file)
    if output_file is None:
        output_path = input_path.parent / (input_path.stem + "_consolidated.ttl")
    else:
        output_path = Path(output_file)

    mapping: dict = {}
    if synonyms_file is not None:
        mapping.update(load_synonym_map(synonyms_file))
    if extra_mapping:
        mapping.update(extra_mapping)

    if not mapping:
        if verbose:
            print("No synonym mappings found — nothing to do.")
        return 0

    if verbose:
        print(f"Loaded {len(mapping)} synonym mapping(s).")

    g = Graph()
    g.parse(input_path, format="turtle")

    triples = list(g)
    g.remove((None, None, None))
    replaced = 0
    for s, p, o in triples:
        new_s = mapping.get(s, s)
        new_p = mapping.get(p, p)
        new_o = mapping.get(o, o)
        if new_s is not s or new_p is not p or new_o is not o:
            replaced += 1
        g.add((new_s, new_p, new_o))

    g.serialize(str(output_path), format="turtle")

    if verbose:
        print(f"Rewrote {replaced} triple(s).  Output: {output_path}")

    return replaced


def main(argv: "list[str] | None" = None) -> None:
    """Apply a synonym IRI mapping to a Turtle RDF file."""
    parser = argparse.ArgumentParser(
        prog="cv-consolidate",
        description=(
            "Rewrite IRIs in a Turtle RDF file using a synonym mapping.\n"
            "Supply synonyms via a Turtle file (--synonyms), inline (--sameas),\n"
            "or both.  Bare slugs in --sameas are expanded to the default\n"
            "namespace <http://example.org/cv/>."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Inline form (--sameas):
              first value = canonical IRI, rest = duplicates merged into it

              cv-consolidate cv.ttl --sameas wh_danone_2011 wh_danone_india wh_danone_india_2011
              cv-consolidate cv.ttl --sameas canonical1 dup1 dup2 --sameas canonical2 dup3

            Synonyms file form (--synonyms):
              @prefix owl: <http://www.w3.org/2002/07/owl#> .
              @prefix :   <http://example.org/cv/> .
              :proj_old    owl:sameAs :proj_canonical .
              :company_old owl:sameAs :company_canonical .

              cv-consolidate graph.ttl --synonyms synonyms.ttl --output fixed.ttl

            Both flags may be combined in one invocation.
        """),
    )
    parser.add_argument("ttl_file", help="Input Turtle file to rewrite.")
    parser.add_argument(
        "--synonyms", "-s", default=None, metavar="FILE",
        help="Turtle file declaring owl:sameAs synonym pairs.",
    )
    parser.add_argument(
        "--sameas", action="append", nargs="+", metavar="IRI",
        help=(
            "CANONICAL DUP [DUP ...]: merge one or more duplicate IRIs into "
            "a canonical IRI.  Repeat the flag for multiple groups."
        ),
    )
    parser.add_argument(
        "--output", "-o", default=None, metavar="FILE",
        help="Output Turtle file (default: <ttl_stem>_consolidated.ttl).",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output.",
    )
    args = parser.parse_args(argv)
    verbose = not args.quiet

    if not args.synonyms and not args.sameas:
        parser.error("provide at least one of --synonyms or --sameas")

    if not Path(args.ttl_file).is_file():
        sys.exit(f"Error: file not found: {args.ttl_file}")
    if args.synonyms and not Path(args.synonyms).is_file():
        sys.exit(f"Error: synonyms file not found: {args.synonyms}")

    # Build inline mapping from --sameas groups
    extra_mapping: dict = {}
    if args.sameas:
        for group in args.sameas:
            if len(group) < 2:
                parser.error(
                    f"--sameas needs at least 2 IRIs (canonical + 1 duplicate), got: {group}"
                )
            canonical = _resolve_iri(group[0])
            for dup in group[1:]:
                dup_iri = _resolve_iri(dup)
                extra_mapping[dup_iri] = canonical

    n = consolidate_synonyms(
        args.ttl_file,
        args.synonyms,
        args.output,
        extra_mapping=extra_mapping or None,
        verbose=verbose,
    )

    if verbose and n == 0:
        print("No IRIs matched the synonym mappings — output is unchanged.")


if __name__ == "__main__":
    main()
