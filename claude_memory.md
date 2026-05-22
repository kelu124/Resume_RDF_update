# claude_memory.md
> Persistent notes for AI assistants working in this repository.

## What this repo does

Converts a CV (PDF, `.txt`, or `.md`) into a **Turtle RDF knowledge graph** using the Anthropic Claude API.

The codebase is structured as an importable Python library (`resume_rdf/`) with two thin wrappers on top:

| Entry-point | Purpose |
|-------------|---------|
| `app.py` | Password-protected Streamlit web app |
| `cv_to_knowledge_graph.py` | CLI script (also installed as `cv-to-rdf` via pyproject.toml) |

## Package structure (as of feat/cv-viz)

```
resume_rdf/
├── __init__.py     public API re-exports + __version__
├── ontology.py     SYSTEM_PROMPT and NAMESPACES dict (single source of truth)
├── parsing.py      build_user_content_from_path/bytes, strip_fences,
│                   count_triples, extract_person_name, validate_turtle
├── cache.py        file-based SHA-256 cache (cache/<hex>.json)
├── api.py          generate_graph_from_file, generate_graph_from_bytes
├── data.py         download_dataset, iter_records, load_records
├── reconcile.py    Entity/Match dataclasses, load_entities, find_matches,
│                   apply_mapping, reconcile_interactive (cross-TTL fuzzy match)
├── qa.py           Question dataclass, audit_experience, update_field
│                   (audit WorkHistory/Project nodes for missing fields; patch TTL)
├── viz.py          visualize_cv(ttl_file, output_path) → Path
│                   HTML (pyvis Barnes-Hut) or PNG/SVG/PDF (networkx + matplotlib)
└── export.py       ttl_to_markdown(ttl_file) → str
                    reconstructs clean Markdown CV from Turtle graph

app.py                      thin Streamlit wrapper (~90 lines)
application_example.py      CLI script (also installed as cv-to-rdf via pyproject.toml)
pyproject.toml              pip-installable package definition
download_data.py            dataset download helper
data/master_resumes.jsonl   1 866 HuggingFace resume records (6 MB, MIT)
llm_cache.py                REMOVED — superseded by resume_rdf/cache.py

shire/                      test fixture CVs
├── frodo_baggins_cv.md     Senior Management Consultant (6 positions)
├── sam_gamgee_cv1.md       Data Engineering Consultant — chronological framing
├── sam_gamgee_cv2.md       Same Sam — ESG/sustainability framing
├── shire_ttl/              Generated TTL files (committed after running notebook)
├── shire_reconciled/       Reconciled TTL copies
└── shire_qa/               QA-patched copies
application_example.ipynb   Two-section notebook: entity reconciliation + CV audit
```

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

### Key predicates

```
:cv  cv:hasWorkHistory    → cv:WorkHistory
                              cvx:hasProject → cvx:Project
                                cvx:usesSkill → cv:Skill   (added feat/project-skill-link)
     cv:hasSkill          → cv:Skill
     cv:hasEducation      → cv:Education
     cvx:hasMOOC          → cvx:MOOC
     cvx:hasTraining      → cvx:Training
     cvx:hasPersonalProject → cvx:PersonalProject
     cvx:hasPublication   → bibo:*
```

## Architecture rules

- **Single SYSTEM_PROMPT**: lives in `resume_rdf/ontology.py`. Any ontology change must be made there only.
- **Cache**: `resume_rdf/cache.py`. SHA-256 of (system, model, content) → `cache/<hex>.json`. Bust by deleting JSON or set `LLM_CACHE_DIR`.
- **Streaming**: always used (`client.messages.stream`) for the large `max_tokens` budget.
- **Default model**: `claude-sonnet-4-6` (`resume_rdf.DEFAULT_MODEL`). Swap for `claude-opus-4-6` for denser CVs.

## CLI commands

| Command | Entry-point | Install extra |
|---------|------------|---------------|
| `cv-to-rdf` | `application_example:main` | (base) |
| `cv-reconcile` | `resume_rdf.reconcile:main` | `reconcile` |
| `cv-audit` | `resume_rdf.qa:audit_main` | `qa` |
| `cv-update` | `resume_rdf.qa:update_main` | `qa` |
| `cv-graph` | `resume_rdf.viz:main` | `viz` |
| `cv-to-md` | `resume_rdf.export:main` | `export` |

`pip install "resume-rdf[all]"` installs all extras.
Key optional extra groups: `app`, `validate`, `reconcile`, `qa`, `viz`, `export`, `dataset`.

## Branch history

| Branch | Change |
|--------|--------|
| `main` | Merged base |
| `feat/project-skill-link` | Added `cvx:usesSkill` predicate |
| `feat/no-email-output` | Removed Gmail SMTP delivery from app.py |
| `feat/resume-dataset` | Added data/master_resumes.jsonl + download_data.py |
| `feat/api-cache` | Added llm_cache.py (later replaced by resume_rdf/cache.py) |
| `feat/library-rearchitecture` | Restructured as importable Python package |
| `feat/entity-reconciliation` | Added reconcile.py + cv-reconcile CLI |
| `feat/cv-qa` | Added qa.py + cv-audit / cv-update CLIs |
| `feat/cv-viz` | Added viz.py (visualize_cv) + export.py (ttl_to_markdown) + cv-graph / cv-to-md CLIs; shire/ test fixtures; application_example.ipynb |

## Key implementation notes

- `GIT_SSL_NO_VERIFY=true` required for all git remote operations in this environment
- `reconcile.py` uses `difflib.SequenceMatcher` (stdlib) — no extra deps for fuzzy matching
- `viz.py`: pyvis for `.html`, networkx + matplotlib for `.png`/`.svg`/`.pdf`; legend injected via HTML string patch (pyvis has no built-in legend API)
- `qa.py`: `startDate`/`endDate` are ambiguous (exist in both `cv:` and `cvx:`); `update_field` checks for existing cvx: triple first to pick the right predicate
- `export.py`: date strings formatted as "Month YYYY"; "present" for open-ended roles
