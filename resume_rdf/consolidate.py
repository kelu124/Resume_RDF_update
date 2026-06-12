"""
resume_rdf.consolidate
======================
``cv-consolidate`` CLI — apply a synonym IRI mapping to a Turtle RDF file.

The synonyms file is a Turtle document containing ``owl:sameAs`` triples.
The *subject* is the old/duplicate IRI; the *object* is the canonical IRI
that replaces it.  Every occurrence of the old IRI — in subject, predicate,
or object position — is rewritten to the canonical IRI::

    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix : <http://example.org/cv/> .

    :proj_duplicate  owl:sameAs :proj_canonical .
    :company_variant owl:sameAs :company_canonical .

Usage::

    cv-consolidate graph.ttl --synonyms synonyms.ttl
    cv-consolidate graph.ttl --synonyms synonyms.ttl --output fixed.ttl
"""

import argparse
import sys
import textwrap
from pathlib import Path


def _require_rdflib() -> None:
    try:
        import rdflib  # noqa: F401
    except ImportError:
        sys.exit(
            "Error: rdflib is required for cv-consolidate.\n"
            "  pip install rdflib\n"
            "  or: pip install 'resume-rdf[validate]'"
        )


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
    synonyms_file: "str | Path",
    output_file: "str | Path | None" = None,
    *,
    verbose: bool = False,
) -> int:
    """Rewrite IRIs in *input_file* according to *synonyms_file*.

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

    mapping = load_synonym_map(synonyms_file)
    if not mapping:
        if verbose:
            print("No owl:sameAs mappings found in synonyms file — nothing to do.")
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
            "The synonyms file declares owl:sameAs pairs; the subject IRI is\n"
            "replaced by the object (canonical) IRI everywhere in the graph."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Synonyms file format (Turtle):
              @prefix owl: <http://www.w3.org/2002/07/owl#> .
              @prefix :   <http://example.org/cv/> .

              :proj_old    owl:sameAs :proj_canonical .
              :company_old owl:sameAs :company_canonical .

            Examples:
              cv-consolidate graph.ttl --synonyms synonyms.ttl
              cv-consolidate graph.ttl --synonyms synonyms.ttl --output fixed.ttl
              cv-consolidate graph.ttl -s synonyms.ttl -o fixed.ttl --quiet
        """),
    )
    parser.add_argument("ttl_file", help="Input Turtle file to rewrite.")
    parser.add_argument(
        "--synonyms", "-s", required=True, metavar="FILE",
        help="Turtle file declaring owl:sameAs synonym pairs.",
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

    if not Path(args.ttl_file).is_file():
        sys.exit(f"Error: file not found: {args.ttl_file}")
    if not Path(args.synonyms).is_file():
        sys.exit(f"Error: synonyms file not found: {args.synonyms}")

    n = consolidate_synonyms(
        args.ttl_file,
        args.synonyms,
        args.output,
        verbose=verbose,
    )

    if verbose and n == 0:
        print("No IRIs matched the synonym mappings — output is unchanged.")


if __name__ == "__main__":
    main()
