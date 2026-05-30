"""
resume_rdf.cli
==============
Entry-point for the ``cv-to-rdf`` command-line tool.

Converts a CV (PDF, Word ``.docx``, ``.txt``, or ``.md``) to a Turtle RDF
knowledge graph using the Anthropic Claude API.  All parsing, caching, and
API logic lives in the ``resume_rdf`` package; this module handles argument
parsing and I/O.

Usage
-----
::

    cv-to-rdf my_cv.pdf
    cv-to-rdf my_cv.docx --output graph.ttl --validate
    cv-to-rdf my_cv.pdf --context "Energy sector, English." --model claude-opus-4-7
    cv-to-rdf my_cv.pdf --max-tokens 80000 --quiet

API key
-------
Set the ``ANTHROPIC_API_KEY`` environment variable (recommended) or pass
``--api-key``.

Word (.docx) support
--------------------
Requires python-docx::

    pip install python-docx
    # or
    pip install "resume-rdf[docx]"
"""

import argparse
import os
import sys
import textwrap

import resume_rdf


def main(argv: list[str] | None = None) -> None:
    """Parse a CV file into Turtle RDF and write it to disk."""
    parser = argparse.ArgumentParser(
        prog="cv-to-rdf",
        description=(
            "Parse a CV into a Turtle RDF knowledge graph using the Anthropic API.\n"
            "Supports PDF, Word (.docx), plain text (.txt), and Markdown (.md) input."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              cv-to-rdf my_cv.pdf
              cv-to-rdf my_cv.docx --output graph.ttl
              cv-to-rdf my_cv.pdf --context "Energy sector, English output." --validate
              cv-to-rdf my_cv.pdf --model claude-opus-4-7 --max-tokens 80000

            Word (.docx) support requires python-docx:
              pip install python-docx
        """),
    )
    parser.add_argument("cv_file", help="Path to the CV file (.pdf, .docx, .txt, or .md).")
    parser.add_argument(
        "--output", "-o", default=None, metavar="FILE",
        help="Output Turtle file (default: <cv_stem>.ttl in the current directory).",
    )
    parser.add_argument(
        "--context", "-c", default="", metavar="TEXT",
        help="Extra context for the parser (e.g. preferred language, industry sectors).",
    )
    parser.add_argument(
        "--api-key", default=None, metavar="KEY",
        help="Anthropic API key (default: ANTHROPIC_API_KEY env var).",
    )
    parser.add_argument(
        "--model", default=resume_rdf.DEFAULT_MODEL, metavar="MODEL",
        help=f"Anthropic model identifier (default: {resume_rdf.DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=resume_rdf.DEFAULT_MAX_TOKENS, metavar="N",
        help=f"Maximum output tokens (default: {resume_rdf.DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate the output Turtle with rdflib after generation.",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output.",
    )
    args = parser.parse_args(argv)
    verbose = not args.quiet

    # Validate inputs
    if not os.path.isfile(args.cv_file):
        sys.exit(f"Error: file not found: {args.cv_file}")

    ext = os.path.splitext(args.cv_file)[1].lower()
    if ext not in {".pdf", ".docx", ".txt", ".md"}:
        sys.exit(f"Error: unsupported file type '{ext}'. Supported: .pdf, .docx, .txt, .md")

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "Error: no API key found.\n"
            "  Set ANTHROPIC_API_KEY, or pass --api-key.\n"
            "  Get a key at: https://console.anthropic.com/settings/keys"
        )

    out_path = args.output or (os.path.splitext(os.path.basename(args.cv_file))[0] + ".ttl")

    if verbose:
        print(f"Input : {args.cv_file}")
        print(f"Output: {out_path}")
        print(f"Model : {args.model}  (max_tokens={args.max_tokens})")

    turtle, usage = resume_rdf.generate_graph_from_file(
        file_path=args.cv_file,
        api_key=api_key,
        extra_context=args.context,
        model=args.model,
        max_tokens=args.max_tokens,
        verbose=verbose,
    )

    if args.validate:
        if verbose:
            print("Validating Turtle...")
        resume_rdf.validate_turtle(turtle)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(turtle)
        f.write("\n")

    if verbose:
        n = resume_rdf.count_triples(turtle)
        name = resume_rdf.extract_person_name(turtle)
        print(f"Saved : {out_path}  (~{n} triples)")
        if name:
            print(f"Person: {name}")
        print(f"Tokens: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")


if __name__ == "__main__":
    main()
