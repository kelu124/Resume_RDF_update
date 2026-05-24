# claude_memory.md
> Persistent notes for AI assistants working in this repository.
> Last updated: 2026-05-23

## What this repo does

Converts a CV (PDF, `.txt`, or `.md`) into a **Turtle RDF knowledge graph** using the Anthropic Claude API.

The codebase is an importable Python library (`resume_rdf/`) with a Streamlit web app (`app.py`) and a standalone demo script (`application_example.py`) on top.

## Package structure

```
resume_rdf/
├── __init__.py     public API re-exports + __version__ = "0.1.0"
├── api.py          generate_graph_from_file, generate_graph_from_bytes
├── cache.py        file-based SHA-256 cache (cache/<hex>.json)
├── cli.py          cv-to-rdf CLI entry-point (thin argparse wrapper)
├── data.py         download_dataset, iter_records, load_records
├── export.py       ttl_to_markdown(ttl_file) → str  (cv-to-md CLI)
├── merge.py        consolidate_ttls(...)  → MergeStats  (cv-merge CLI)
├── ontology.py     SYSTEM_PROMPT and NAMESPACES dict (single source of truth)
├── parsing.py      build_user_content_from_path/bytes, strip_fences,
│                   count_triples, extract_person_name, validate_turtle
├── qa.py           Question dataclass, audit_experience, update_field
│                   (cv-audit / cv-update CLIs)
├── reconcile.py    Entity/Match dataclasses, load_entities, find_matches,
│                   apply_mapping, reconcile_interactive  (cv-reconcile CLI)
└── viz.py          visualize_cv(ttl_file, output_path) → Path  (cv-graph CLI)

app.py                      Streamlit web app (password-gated, thin UI wrapper)
application_example.py      Standalone 9-step demo script using shire/ fixtures
application_example.ipynb   Notebook version of the same demo (Sections 1–4)
pyproject.toml              pip-installable package definition
data/master_resumes.jsonl   1 866 HuggingFace resume records (MIT)

shire/                      Test fixture CVs
├── frodo_baggins_cv.md     Senior Management Consultant (6 positions)
├── sam_gamgee_cv1.md       Data Engineering Consultant — chronological framing
├── sam_gamgee_cv2.md       Same Sam — ESG/sustainability framing
├── shire_ttl/              Generated TTL files
├── shire_reconciled/       Reconciled TTL copies
├── shire_qa/               QA-patched copies
├── shire_merged/           Merged (same-person) TTL output
└── reconstructed/          TTL → Markdown reconstructions
```

## application_example.py — end-to-end demo flow

Runs the full pipeline using the `shire/` CVs, outputs to `shire/output/`:

| Step | Function | What it does |
|------|----------|--------------|
| 1 | `step1_generate_ttl` | Convert 3 Markdown CVs → Turtle (cached) |
| 2 | `step2_inspect_entities` | Extract and print projects + companies |
| 3 | `step3_reconcile` | Cross-file IRI reconciliation (auto-accept) |
| 4 | `step4_audit` | Audit each TTL for missing fields |
| 5 | `step5_update` | Fill one missing field with `update_field` |
| 6 | `step6_merge` | Consolidate sam_v1 + sam_v2 → `sam_merged.ttl` |
| 7 | `step7_visualize` | Render all graphs as interactive HTML |
| 8 | `step8_export` | Export all TTLs to Markdown |
| 9 | `step9_summary` | Print file listing with sizes |

Run: `python application_example.py` (requires `ANTHROPIC_API_KEY`)

## app.py — Streamlit web app flow (4-step pipeline)

Rewrote 2026-05-24. State machine driven by `st.session_state["step"]` (1–4).

| Step | Key session state | What happens |
|------|-------------------|-------------|
| 1 · Upload | `ttl_files: list[(name, path_str)]` | Upload .pdf/.txt/.md/.ttl/.docx; TTLs used as-is, others parsed via Claude; ZIP download of all TTLs |
| 2 · Consolidate | `working_path`, `merge_stats` | `consolidate_ttls()` with strategy selector; shows metrics + download; skipped if only 1 TTL |
| 3 · QA Chat | `chat_history`, `pending_questions`, `current_q` | `audit_experience()` → questions in chat; answers applied via `update_field()`; type 'done' to skip |
| 4 · Export | `exports: {ttl_bytes, md, html_bytes, zip_bytes}` | `ttl_to_markdown()` + `visualize_cv()` → ZIP package; preview both outputs inline |

Helper functions: `_tmpdir()`, `_go(step)`, `_reset()`, `_make_zip()`, `_docx_to_bytes()`.
All file I/O goes through a per-session `tempfile.mkdtemp()` directory.

## CLI commands

| Command | Entry-point | `pip install "resume-rdf[…]"` |
|---------|------------|-------------------------------|
| `cv-to-rdf` | `resume_rdf.cli:main` | (base) |
| `cv-reconcile` | `resume_rdf.reconcile:main` | `reconcile` |
| `cv-audit` | `resume_rdf.qa:audit_main` | `qa` |
| `cv-update` | `resume_rdf.qa:update_main` | `qa` |
| `cv-graph` | `resume_rdf.viz:main` | `viz` |
| `cv-to-md` | `resume_rdf.export:main` | `export` |
| `cv-merge` | `resume_rdf.merge:main` | `merge` |

`pip install "resume-rdf[all]"` installs all extras.

## Ontology map

| Prefix | Base URI | Role |
|--------|----------|------|
| `cv:` | `http://purl.org/captsolo/resume-rdf/0.2/cv#` | ResumeRDF core: Person, WorkHistory, Company, Skill, Education |
| `cvb:` | `http://purl.org/captsolo/resume-rdf/0.2/base#` | ResumeRDF base taxonomy (declared but lightly used) |
| `cvx:` | `http://example.org/cv-extension#` | Custom extension: Project, MOOC, Training, PersonalProject |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Person identity |
| `bibo:` | `http://purl.org/ontology/bibo/` | Publications |
| `dcterms:` | `http://purl.org/dc/terms/` | Publication metadata |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals |

### Key graph structure

```
:cv  cv:hasWorkHistory    → cv:WorkHistory
                              cvx:hasProject → cvx:Project
                                cvx:usesSkill → cv:Skill
     cv:hasSkill          → cv:Skill
     cv:hasEducation      → cv:Education
     cvx:hasMOOC          → cvx:MOOC
     cvx:hasTraining      → cvx:Training
     cvx:hasPersonalProject → cvx:PersonalProject
     cvx:hasPublication   → bibo:*
```

## Architecture rules

- **Single SYSTEM_PROMPT**: lives in `resume_rdf/ontology.py`. Any ontology change must be made there only.
- **Cache**: `resume_rdf/cache.py`. SHA-256 of (system, model, content) → `cache/<hex>.json`. LLM merge results in `cache/merge_<sha256>.json`. Bust by deleting JSON or set `LLM_CACHE_DIR`.
- **Streaming**: always used (`client.messages.stream`) for the large `max_tokens` budget.
- **Default model**: `claude-sonnet-4-6` (`resume_rdf.DEFAULT_MODEL`). Merge LLM calls default to `claude-haiku-4-5-20251001`.

## Key implementation notes

- `GIT_SSL_NO_VERIFY=true` required for all git remote operations in this environment
- `reconcile.py` uses `difflib.SequenceMatcher` (stdlib) — no extra deps for fuzzy matching
- `viz.py`: pyvis for `.html`, networkx + matplotlib for `.png`/`.svg`/`.pdf`; legend injected via HTML string patch (pyvis has no built-in legend API)
- `qa.py`: `startDate`/`endDate` are ambiguous (exist in both `cv:` and `cvx:`); `update_field` checks for existing `cvx:` triple first to pick the right predicate
- `export.py`: date strings formatted as "Month YYYY"; "present" for open-ended roles
- `merge.py`: reuses `reconcile.py` for IRI unification (threshold 0.70). Three strategies for description-type predicates: `longest` (default), `concat` (join with " | "), `llm` (Claude synthesis, cached). Date predicates always use built-in heuristics. URI objects always union. `MergeStats` tracks `llm_calls` and `llm_cache_hits`.

## Branch history (all merged — only `main` remains)

| Branch | Change |
|--------|--------|
| `feat/project-skill-link` | Added `cvx:usesSkill` predicate |
| `feat/no-email-output` | Removed Gmail SMTP delivery from app.py |
| `feat/resume-dataset` | Added data/master_resumes.jsonl |
| `feat/api-cache` | Added cache.py (replaced old llm_cache.py) |
| `feat/library-rearchitecture` | Restructured as importable Python package |
| `feat/entity-reconciliation` | Added reconcile.py + cv-reconcile CLI |
| `feat/cv-qa` | Added qa.py + cv-audit / cv-update CLIs |
| `feat/cv-viz` | Added viz.py, export.py, merge.py; shire/ fixtures; notebooks |
