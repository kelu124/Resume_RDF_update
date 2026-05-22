# claude_memory.md
> Persistent notes for AI assistants working in this repository.

## What this repo does

Converts a CV (PDF, `.txt`, or `.md`) into a **Turtle RDF knowledge graph** using the Anthropic Claude API.

The codebase is structured as an importable Python library (`resume_rdf/`) with two thin wrappers on top:

| Entry-point | Purpose |
|-------------|---------|
| `app.py` | Password-protected Streamlit web app |
| `cv_to_knowledge_graph.py` | CLI script (also installed as `cv-to-rdf` via pyproject.toml) |

## Package structure (as of feat/library-rearchitecture)

```
resume_rdf/
├── __init__.py     public API re-exports + __version__
├── ontology.py     SYSTEM_PROMPT and NAMESPACES dict (single source of truth)
├── parsing.py      build_user_content_from_path/bytes, strip_fences,
│                   count_triples, extract_person_name, validate_turtle
├── cache.py        file-based SHA-256 cache (cache/<hex>.json)
├── api.py          generate_graph_from_file, generate_graph_from_bytes
└── data.py         download_dataset, iter_records, load_records

app.py                      thin Streamlit wrapper (~90 lines)
cv_to_knowledge_graph.py    thin CLI wrapper (~80 lines)
pyproject.toml              pip-installable package definition
download_data.py            dataset download helper
data/master_resumes.jsonl   1 866 HuggingFace resume records (6 MB, MIT)
llm_cache.py                REMOVED — superseded by resume_rdf/cache.py
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

## Branch history

| Branch | Change |
|--------|--------|
| `main` | Merged base |
| `feat/project-skill-link` | Added `cvx:usesSkill` predicate |
| `feat/no-email-output` | Removed Gmail SMTP delivery from app.py |
| `feat/resume-dataset` | Added data/master_resumes.jsonl + download_data.py |
| `feat/api-cache` | Added llm_cache.py (later replaced by resume_rdf/cache.py) |
| `feat/library-rearchitecture` | Restructured as importable Python package |
