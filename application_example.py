"""
cv_to_knowledge_graph.py  —  CLI entry-point
============================================
Thin wrapper around the ``resume_rdf`` library.  All parsing, caching, and
API logic lives in the package; this file handles argument parsing and I/O.

Run:  streamlit run app.py          (web UI)
      python cv_to_knowledge_graph.py my_cv.pdf   (CLI)

Usage
-----
  python cv_to_knowledge_graph.py my_cv.pdf
  python cv_to_knowledge_graph.py my_cv.pdf --output graph.ttl
  python cv_to_knowledge_graph.py my_cv.pdf \\
      --context "Energy sector, English labels." --validate
  python cv_to_knowledge_graph.py my_cv.pdf --model claude-opus-4-6
  python cv_to_knowledge_graph.py my_cv.pdf --max-tokens 60000

API key: set ANTHROPIC_API_KEY or pass --api-key.
"""

import argparse
import os
import sys
import textwrap

import resume_rdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a CV into a Turtle RDF knowledge graph using the Anthropic API.\n"
            "Supports PDF, plain text (.txt), and Markdown (.md) input."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              python cv_to_knowledge_graph.py my_cv.pdf
              python cv_to_knowledge_graph.py my_cv.pdf --output graph.ttl
              python cv_to_knowledge_graph.py my_cv.pdf \\
                  --context "Energy and transport. Use English." --validate
              python cv_to_knowledge_graph.py my_cv.pdf --model claude-opus-4-6
        """),
    )
    parser.add_argument("cv_file", help="Path to the CV file (.pdf, .txt, or .md).")
    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="Output Turtle file (default: <cv_stem>.ttl).")
    parser.add_argument("--context", "-c", default="", metavar="TEXT",
                        help="Extra context for the parser.")
    parser.add_argument("--api-key", default=None, metavar="KEY",
                        help="Anthropic API key (default: ANTHROPIC_API_KEY env var).")
    parser.add_argument("--model", default=resume_rdf.DEFAULT_MODEL, metavar="MODEL",
                        help=f"Anthropic model (default: {resume_rdf.DEFAULT_MODEL}).")
    parser.add_argument("--max-tokens", type=int, default=resume_rdf.DEFAULT_MAX_TOKENS,
                        metavar="N", help=f"Max output tokens (default: {resume_rdf.DEFAULT_MAX_TOKENS}).")
    parser.add_argument("--validate", action="store_true",
                        help="Validate output Turtle with rdflib (requires: pip install rdflib).")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress progress output.")

    args = parser.parse_args()
    verbose = not args.quiet

    out_path = args.output or (os.path.splitext(os.path.basename(args.cv_file))[0] + ".ttl")

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "Error: no Anthropic API key found.\n"
            "  Set the ANTHROPIC_API_KEY environment variable, or use --api-key.\n"
            "  Get a key at: https://console.anthropic.com/settings/keys"
        )

    if not os.path.isfile(args.cv_file):
        sys.exit(f"Error: file not found: {args.cv_file}")

    ext = os.path.splitext(args.cv_file)[1].lower()
    if ext not in {".pdf", ".txt", ".md"}:
        sys.exit(f"Error: unsupported file type '{ext}'. Use .pdf, .txt, or .md.")

    if verbose:
        print(f"Input:   {args.cv_file}")
        print(f"Output:  {out_path}")
        print(f"Model:   {args.model}  (max_tokens={args.max_tokens})")

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
        print(f"Saved:   {out_path}  (~{n} triple statements)")
        if name:
            print(f"Person:  {name}")
        print(f"Tokens:  {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")


if __name__ == "__main__":
    main()
