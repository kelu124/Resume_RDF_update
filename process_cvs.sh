#!/usr/bin/env bash
# process_cvs.sh
# ==============
# Convert all CV files (.pdf, .docx) in a folder to a single merged TTL.
#
# Usage:
#   ./process_cvs.sh <folder> [options]
#
# Options:
#   -o, --output FILE     Output TTL file  (default: <folder>/master_cv.ttl)
#   -c, --context TEXT    Extra context hint for the parser
#   -s, --strategy STR    Merge strategy: longest|concat|llm  (default: llm)
#   -h, --help            Show this help
#
# Environment:
#   ANTHROPIC_API_KEY     Required — your Anthropic API key
#
# Examples:
#   ./process_cvs.sh cvs/
#   ./process_cvs.sh cvs/ --output cvs/team.ttl
#   ./process_cvs.sh cvs/ --strategy concat --context "Energy sector, UK"
#   ./process_cvs.sh cvs/ --strategy llm --output cvs/enriched.ttl
#
# Requirements:
#   pip install "resume-rdf[all]"   (installs cv-to-rdf and cv-merge CLIs)

set -uo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
OUTPUT=""   # resolved to <folder>/master_cv.ttl after arg parsing
CONTEXT=""
STRATEGY="llm"
FOLDER=""

# ── usage ─────────────────────────────────────────────────────────────────────
usage() {
    grep "^#" "$0" | grep -v "^#!/" | sed 's/^# \{0,1\}//'
}

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            OUTPUT="$2"; shift 2 ;;
        -c|--context)
            CONTEXT="$2"; shift 2 ;;
        -s|--strategy)
            STRATEGY="$2"; shift 2 ;;
        -h|--help)
            usage; exit 0 ;;
        -*)
            echo "Unknown option: $1" >&2; echo "Run with --help for usage." >&2; exit 1 ;;
        *)
            if [[ -n "$FOLDER" ]]; then
                echo "Error: unexpected argument '$1'" >&2; exit 1
            fi
            FOLDER="$1"; shift ;;
    esac
done

# ── validation ────────────────────────────────────────────────────────────────
if [[ -z "$FOLDER" ]]; then
    echo "Error: folder argument is required." >&2
    echo "Run with --help for usage." >&2
    exit 1
fi

if [[ ! -d "$FOLDER" ]]; then
    echo "Error: folder not found: $FOLDER" >&2
    exit 1
fi

# Default output: master_cv.ttl inside the input folder
if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$FOLDER/master_cv.ttl"
fi

# ── load API key from .env if not already in environment ──────────────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for _env_candidate in ".env" "$SCRIPT_DIR/.env"; do
        if [[ -f "$_env_candidate" ]]; then
            _val=$(grep -E '^ANTHROPIC_API_KEY=' "$_env_candidate" | head -1 | cut -d'=' -f2-)
            # Strip optional surrounding quotes
            _val="${_val#[\"\']}"
            _val="${_val%[\"\']}"
            if [[ -n "$_val" ]]; then
                ANTHROPIC_API_KEY="$_val"
                echo "Loaded ANTHROPIC_API_KEY from $_env_candidate"
                break
            fi
        fi
    done
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY is not set." >&2
    echo "  Option 1 — export in your shell:  export ANTHROPIC_API_KEY='sk-ant-...'" >&2
    echo "  Option 2 — add to a .env file:    echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env" >&2
    exit 1
fi

if [[ "$STRATEGY" != "longest" && "$STRATEGY" != "concat" && "$STRATEGY" != "llm" ]]; then
    echo "Error: --strategy must be one of: longest, concat, llm" >&2
    exit 1
fi

# ── locate CLIs ───────────────────────────────────────────────────────────────
CV_TO_RDF=$(command -v cv-to-rdf 2>/dev/null || true)
CV_MERGE=$(command -v cv-merge 2>/dev/null || true)

if [[ -z "$CV_TO_RDF" ]]; then
    echo "Error: cv-to-rdf not found." >&2
    echo "Install with:  pip install \"resume-rdf[all]\"" >&2
    exit 1
fi
if [[ -z "$CV_MERGE" ]]; then
    echo "Error: cv-merge not found." >&2
    echo "Install with:  pip install \"resume-rdf[all]\"" >&2
    exit 1
fi

# ── find CV files ─────────────────────────────────────────────────────────────
# Collect .pdf and .docx files (case-insensitive) from the top level of FOLDER
CV_FILES=()
while IFS= read -r -d '' f; do
    CV_FILES+=("$f")
done < <(find "$FOLDER" -maxdepth 1 \( -iname "*.pdf" -o -iname "*.docx" -o -iname "*.doc" \) -print0 | sort -z)

if [[ ${#CV_FILES[@]} -eq 0 ]]; then
    echo "No .pdf or .docx files found in: $FOLDER" >&2
    exit 1
fi

echo "Found ${#CV_FILES[@]} CV file(s) in '$FOLDER'"
echo ""

# ── parse each CV to TTL (output alongside source file) ──────────────────────
# e.g. folder/cv1.docx → folder/cv1.docx.ttl
TTL_FILES=()
FAILED=0

for cv_file in "${CV_FILES[@]}"; do
    filename=$(basename "$cv_file")
    out_ttl="${cv_file}.ttl"

    if [[ -f "$out_ttl" && -s "$out_ttl" ]]; then
        echo "→ Skipping: $filename  (TTL already exists)"
        TTL_FILES+=("$out_ttl")
        echo ""
        continue
    fi

    echo "→ Parsing: $filename"

    _context="CV process output MUST BE in English."
    if [[ -n "$CONTEXT" ]]; then
        _context="$_context $CONTEXT"
    fi
    parse_args=("$cv_file" "--output" "$out_ttl" "--context" "$_context")

    if "$CV_TO_RDF" "${parse_args[@]}"; then
        if [[ -f "$out_ttl" && -s "$out_ttl" ]]; then
            TTL_FILES+=("$out_ttl")
            echo "  ✓ Saved: $(basename "$out_ttl")"
        else
            echo "  ✗ Output file is empty — skipping." >&2
            (( FAILED++ )) || true
        fi
    else
        echo "  ✗ cv-to-rdf failed for: $filename" >&2
        (( FAILED++ )) || true
    fi
    echo ""
done

if [[ ${#TTL_FILES[@]} -eq 0 ]]; then
    echo "Error: no TTL files were generated." >&2
    exit 1
fi

if [[ $FAILED -gt 0 ]]; then
    echo "Warning: $FAILED file(s) failed to parse and will be excluded." >&2
    echo ""
fi

# ── reconcile cross-file entity IRIs before merging ──────────────────────────
CV_RECONCILE=$(command -v cv-reconcile 2>/dev/null || true)
if [[ -n "$CV_RECONCILE" && ${#TTL_FILES[@]} -gt 1 ]]; then
    echo "Running cross-file entity reconciliation…"
    "$CV_RECONCILE" "${TTL_FILES[@]}" --yes
    echo "Done.  IRI reconciliation applied to source TTLs."
elif [[ ${#TTL_FILES[@]} -le 1 ]]; then
    true  # single file — no cross-file reconciliation needed
else
    echo "Note: cv-reconcile not found — skipping cross-file IRI reconciliation."
    echo "Install with:  pip install \"resume-rdf[all]\""
fi
echo ""

# ── merge (or copy if only one TTL) ──────────────────────────────────────────
if [[ ${#TTL_FILES[@]} -eq 1 ]]; then
    echo "Single TTL generated — copying to: $OUTPUT"
    cp "${TTL_FILES[0]}" "$OUTPUT"
else
    echo "Merging ${#TTL_FILES[@]} TTL files (strategy: $STRATEGY) → $OUTPUT"
    "$CV_MERGE" "${TTL_FILES[@]}" --output "$OUTPUT" --strategy "$STRATEGY"
fi

echo ""
echo "Done.  Output written to: $OUTPUT"
echo ""

# ── generate markdown CV ──────────────────────────────────────────────────────
CV_TO_MD=$(command -v cv-to-md 2>/dev/null || true)
if [[ -n "$CV_TO_MD" ]]; then
    MD_OUTPUT="${OUTPUT%.ttl}.md"
    echo "Generating Markdown CV → $MD_OUTPUT"
    "$CV_TO_MD" "$OUTPUT" --output "$MD_OUTPUT"
    echo "Done.  Markdown written to: $MD_OUTPUT"
else
    echo "Note: cv-to-md not found — skipping Markdown export."
    echo "Install with:  pip install \"resume-rdf[all]\""
fi

# ── audit the consolidated CV ─────────────────────────────────────────────────
CV_AUDIT=$(command -v cv-audit 2>/dev/null || true)
if [[ -n "$CV_AUDIT" ]]; then
    echo ""
    echo "Auditing consolidated CV → $OUTPUT"
    "$CV_AUDIT" "$OUTPUT"
else
    echo "Note: cv-audit not found — skipping audit."
    echo "Install with:  pip install \"resume-rdf[all]\""
fi
