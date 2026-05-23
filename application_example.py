"""
application_example.py
======================
End-to-end demonstration of the ``resume_rdf`` library.

Runs through the complete pipeline using the fictional consultant CVs in
``shire/`` as test data:

    1.  Convert three Markdown CVs to Turtle RDF (cached after first run)
    2.  Extract and display entities across all three graphs
    3.  Run cross-file entity reconciliation (auto-accept all matches)
    4.  Audit each CV for missing fields
    5.  Fill one missing field with ``update_field``
    6.  Consolidate Sam's two CV versions into one enriched TTL
    7.  Visualise every graph as an interactive HTML file
    8.  Export every TTL to Markdown
    9.  Print a summary

Run with:
    python application_example.py

Requirements:
    pip install -e ".[all]"
    export ANTHROPIC_API_KEY="sk-ant-..."

The shire/ directory must be present (it is checked into the repository).
All outputs are written to shire/output/.
"""

import os
import shutil
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────────────

try:
    import resume_rdf
    from resume_rdf import (
        audit_experience,
        consolidate_ttls,
        count_triples,
        extract_person_name,
        find_matches,
        generate_graph_from_file,
        load_entities,
        reconcile_interactive,
        ttl_to_markdown,
        update_field,
        visualize_cv,
    )
except ImportError as exc:
    sys.exit(
        f"Import error: {exc}\n"
        "Install the library with:  pip install -e \".[all]\""
    )


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SHIRE_DIR  = Path("shire")
OUTPUT_DIR = SHIRE_DIR / "output"
TTL_DIR    = OUTPUT_DIR / "ttl"
VIZ_DIR    = OUTPUT_DIR / "viz"
MD_DIR     = OUTPUT_DIR / "md"
MERGE_DIR  = OUTPUT_DIR / "merged"

CVS = {
    "frodo":  SHIRE_DIR / "frodo_baggins_cv.md",
    "sam_v1": SHIRE_DIR / "sam_gamgee_cv1.md",
    "sam_v2": SHIRE_DIR / "sam_gamgee_cv2.md",
}

EXTRA_CONTEXT = "UK consultant CVs, energy and data engineering sectors. Output in English."


def _require_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        sys.exit(
            "Error: ANTHROPIC_API_KEY is not set.\n"
            "Export it before running:  export ANTHROPIC_API_KEY='sk-ant-...'"
        )
    return key


def _banner(title: str) -> None:
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def _check_shire_dir() -> None:
    if not SHIRE_DIR.exists():
        sys.exit(
            "Error: shire/ directory not found.\n"
            "Run this script from the root of the Resume_RDF_update repository."
        )
    missing = [name for name, path in CVS.items() if not path.exists()]
    if missing:
        sys.exit(f"Error: missing CV files in shire/: {missing}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Convert CVs to Turtle RDF
# ─────────────────────────────────────────────────────────────────────────────

def step1_generate_ttl(api_key: str) -> dict[str, Path]:
    _banner("Step 1 — Convert Markdown CVs to Turtle RDF")

    TTL_DIR.mkdir(parents=True, exist_ok=True)
    ttl_paths: dict[str, Path] = {}

    for name, cv_path in CVS.items():
        out = TTL_DIR / f"{name}.ttl"
        if out.exists():
            n = count_triples(out.read_text(encoding="utf-8"))
            print(f"  {name}: using cached {out.name}  ({n} triples)")
        else:
            print(f"  {name}: converting {cv_path.name} ...")
            turtle, usage = generate_graph_from_file(
                cv_path,
                api_key=api_key,
                extra_context=EXTRA_CONTEXT,
            )
            out.write_text(turtle, encoding="utf-8")
            print(
                f"    → {out.name}  "
                f"({count_triples(turtle)} triples, "
                f"{usage['output_tokens']:,} tokens)"
            )
        ttl_paths[name] = out

    return ttl_paths


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Extract entities
# ─────────────────────────────────────────────────────────────────────────────

def step2_inspect_entities(ttl_paths: dict[str, Path]) -> None:
    _banner("Step 2 — Extract and display entities")

    all_files = list(ttl_paths.values())
    entities = load_entities(all_files)

    for kind in ("project", "company"):
        subset = [e for e in entities if e.kind == kind]
        print(f"\n  {kind.upper()} ({len(subset)}):")
        for e in subset:
            print(f"    [{e.source.name}]  {e.label!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Entity reconciliation
# ─────────────────────────────────────────────────────────────────────────────

def step3_reconcile(ttl_paths: dict[str, Path]) -> dict[str, Path]:
    _banner("Step 3 — Cross-file entity reconciliation")

    rec_dir = OUTPUT_DIR / "reconciled"
    if rec_dir.exists():
        shutil.rmtree(rec_dir)
    shutil.copytree(TTL_DIR, rec_dir)

    rec_paths = sorted(rec_dir.glob("*.ttl"))
    entities = load_entities(rec_paths)
    matches = find_matches(entities, threshold=0.65)
    print(f"  Found {len(matches)} candidate pair(s) at ≥65% similarity")

    n_merged = reconcile_interactive(
        rec_paths,
        threshold=0.65,
        auto_yes=True,
    )
    print(f"  Applied {n_merged} IRI mapping(s)")

    return {
        name: rec_dir / f"{name}.ttl"
        for name in ttl_paths
    }


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Audit for missing fields
# ─────────────────────────────────────────────────────────────────────────────

def step4_audit(ttl_paths: dict[str, Path]) -> None:
    _banner("Step 4 — Audit CVs for missing fields")

    for name, path in ttl_paths.items():
        questions = audit_experience(path)
        status = f"{len(questions)} question(s)" if questions else "no gaps found ✓"
        print(f"\n  {name} — {status}")
        for q in questions:
            print(f"    [{q.slug}]  {q.field}")
            print(f"      {q.question}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Fill a missing field
# ─────────────────────────────────────────────────────────────────────────────

def step5_update(ttl_paths: dict[str, Path]) -> None:
    _banner("Step 5 — Fill a missing field with update_field")

    # Work on a copy of frodo's TTL
    patch_dir = OUTPUT_DIR / "patched"
    patch_dir.mkdir(parents=True, exist_ok=True)
    frodo_patched = patch_dir / "frodo_patched.ttl"
    shutil.copy(ttl_paths["frodo"], frodo_patched)

    before = audit_experience(frodo_patched)
    if not before:
        print("  No missing fields in frodo — nothing to update.")
        return

    q = before[0]
    print(f"  Filling [{q.slug}].{q.field} …")

    sample_values = {
        "endDate":           "present",
        "startDate":         "2025-01-01",
        "jobTitle":          "Senior Consultant",
        "jobDescription":    "Led strategic engagements across energy and financial services clients.",
        "benefitsDelivered": "Delivered measurable outcomes across all assigned projects.",
        "roleTitle":         "Programme Lead",
        "projectDescription": "Strategic programme delivery and stakeholder management.",
        "activitiesPerformed": "Managed programme governance and ran stakeholder workshops.",
    }

    value = sample_values.get(q.field, "To be confirmed")
    update_field(frodo_patched, q.slug, q.field, value)

    after = audit_experience(frodo_patched)
    print(f"  Before: {len(before)} question(s)  →  After: {len(after)} question(s)")
    print(f"  Set {q.field} = {value!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Consolidate Sam's two CVs
# ─────────────────────────────────────────────────────────────────────────────

def step6_merge(ttl_paths: dict[str, Path]) -> Path:
    _banner("Step 6 — Consolidate Sam v1 + Sam v2 into one enriched TTL")

    MERGE_DIR.mkdir(parents=True, exist_ok=True)
    merged_path = MERGE_DIR / "sam_merged.ttl"

    stats = consolidate_ttls(
        [ttl_paths["sam_v1"], ttl_paths["sam_v2"]],
        merged_path,
        threshold=0.70,
        strategy="longest",
    )

    print(f"  Input  : {stats.input_files} files, {stats.input_triples} triples")
    print(f"  IRIs unified    : {stats.iri_mappings}")
    print(f"  Conflicts resolved: {stats.conflicts_resolved}")
    print(f"  Output : {stats.output_triples} triples → {merged_path.name}")

    return merged_path


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Visualise all graphs
# ─────────────────────────────────────────────────────────────────────────────

def step7_visualize(ttl_paths: dict[str, Path], sam_merged: Path) -> None:
    _banner("Step 7 — Generate interactive HTML graph visualisations")

    VIZ_DIR.mkdir(parents=True, exist_ok=True)

    graphs = {**ttl_paths, "sam_merged": sam_merged}
    for name, ttl_path in graphs.items():
        out = VIZ_DIR / f"{name}.html"
        visualize_cv(ttl_path, out)
        print(f"  {name}: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Export to Markdown
# ─────────────────────────────────────────────────────────────────────────────

def step8_export(ttl_paths: dict[str, Path], sam_merged: Path) -> None:
    _banner("Step 8 — Export Turtle graphs to Markdown")

    MD_DIR.mkdir(parents=True, exist_ok=True)

    graphs = {**ttl_paths, "sam_merged": sam_merged}
    for name, ttl_path in graphs.items():
        md = ttl_to_markdown(ttl_path)
        out = MD_DIR / f"{name}.md"
        out.write_text(md, encoding="utf-8")
        name_str = extract_person_name(ttl_path.read_text(encoding="utf-8")) or name
        print(f"  {name_str}: {out}  ({len(md):,} chars)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Summary
# ─────────────────────────────────────────────────────────────────────────────

def step9_summary() -> None:
    _banner("Step 9 — Summary")

    for folder, label in [
        (TTL_DIR,    "Turtle RDF files"),
        (VIZ_DIR,    "Graph visualisations"),
        (MD_DIR,     "Markdown exports"),
        (MERGE_DIR,  "Merged TTL"),
    ]:
        files = sorted(folder.glob("*")) if folder.exists() else []
        print(f"\n  {label} ({len(files)}):")
        for f in files:
            size = f.stat().st_size
            print(f"    {f.name}  ({size:,} bytes)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("resume_rdf — end-to-end demonstration")
    print(f"Library version: {resume_rdf.__version__}")

    _check_shire_dir()
    api_key = _require_api_key()

    # Create clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    ttl_paths  = step1_generate_ttl(api_key)
    step2_inspect_entities(ttl_paths)
    rec_paths  = step3_reconcile(ttl_paths)
    step4_audit(rec_paths)
    step5_update(ttl_paths)
    sam_merged = step6_merge(ttl_paths)
    step7_visualize(ttl_paths, sam_merged)
    step8_export(ttl_paths, sam_merged)
    step9_summary()

    print()
    print("Done.  All outputs written to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
