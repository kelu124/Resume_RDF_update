# resume-rdf — LLM agent guide

This document is written for LLM agents that need to invoke, orchestrate, or extend
the `resume-rdf` toolkit programmatically.

---

## What the tool does

Converts CV/resume documents to structured Turtle RDF knowledge graphs, then
provides tools to deduplicate, merge, reconcile, export, and audit those graphs.

**Primary use cases:**
- Parse one or more CVs (PDF/DOCX/DOC/MD/TXT) into queryable RDF
- Merge multiple CVs of the *same person* into one enriched graph
- Reconcile shared entity IRIs across CVs of *different people* (e.g. shared employers or projects)
- Export a graph back to readable Markdown
- Audit a graph for missing fields

---

## Installation

```bash
pip install "resume-rdf[all]"
export ANTHROPIC_API_KEY="sk-ant-..."
```

Requires Python ≥ 3.10.  The `[all]` extra installs every optional dependency
(rdflib, streamlit, pyvis, datasets).  Individual extras: `[validate]`, `[merge]`,
`[reconcile]`, `[export]`, `[viz]`, `[qa]`, `[app]`, `[dataset]`.

---

## CLI reference

### `cv-to-rdf` — parse a CV to Turtle

```
cv-to-rdf <FILE> [--output OUT.ttl] [--context TEXT] [--model MODEL]
          [--api-key KEY] [--max-tokens N] [--validate] [--quiet] [--overwrite]
```

| Param | Default | Notes |
|-------|---------|-------|
| `FILE` | — | `.pdf`, `.docx`, `.doc`, `.md`, `.txt` |
| `--output` | `<FILE>.ttl` | Output path |
| `--context` | `""` | Appended to system prompt; inject domain hints or language instructions |
| `--model` | `claude-sonnet-4-6` | Any Anthropic model |
| `--max-tokens` | 16000 | Increase for very long CVs |
| `--validate` | off | Parse output with rdflib and exit non-zero if invalid |
| `--overwrite` | off | Overwrite output file if it already exists (default: skip and exit 0) |

**Output:** A `.ttl` file containing a self-contained Turtle RDF graph.  Always
starts with `@prefix` declarations.  Results are cached by content hash in
`cache/<sha256>.json`; re-running the same input is free.

**Gotcha — language:** The model defaults to the CV's language.  Always pass
`--context "CV process output MUST BE in English."` for a multilingual corpus.

**Gotcha — `.doc` files:** Requires `antiword` or `catdoc` installed on the system
(`apt install antiword`).  Without them, `.doc` parsing raises a `RuntimeError`.

---

### `cv-merge` — merge same-person CVs

```
cv-merge FILE1.ttl FILE2.ttl [FILE3.ttl ...] --output OUT.ttl
         [--strategy longest|concat|llm] [--threshold FLOAT]
         [--master FILE.ttl] [--api-key KEY] [--model MODEL] [--verbose]
```

**Use only for the same person.**  For different people sharing a corpus, use
`cv-reconcile` instead (see below).

| Param | Default | Notes |
|-------|---------|-------|
| `--strategy` | `longest` | How to resolve conflicting description fields |
| `--threshold` | `0.70` | Similarity threshold for internal entity reconciliation |
| `--master` | first file | File whose IRIs are kept as canonical |

**Strategies:**
- `longest` — keep the longest string; fast, no API calls
- `concat` — join all unique values with ` | `; zero loss, can be verbose
- `llm` — Claude synthesises one coherent description; best quality; cached

**Output:** Single `.ttl` with all triples merged.  URI-valued objects (skill links,
type links) are always unioned.  `startDate` → earliest; `endDate` → latest or
`"present"`.

**Returns (`MergeStats`):** `input_files`, `input_triples`, `iri_mappings`,
`conflicts_resolved`, `output_triples`, `llm_calls`, `llm_cache_hits`,
`dedup_removed`.

---

### `cv-reconcile` — unify IRIs across multiple CVs

```
cv-reconcile FILE1.ttl FILE2.ttl [FILE3.ttl ...]
             [--threshold FLOAT] [--yes] [--dry-run] [--master FILE.ttl]
```

Finds near-duplicate `cvx:Project` and `cv:Company` entities across files, surfaces
them for confirmation, then rewrites the TTL files in-place.

| Param | Default | Notes |
|-------|---------|-------|
| `--threshold` | `0.75` | Minimum similarity to surface a pair |
| `--yes` | off | Accept all matches automatically (batch mode) |
| `--dry-run` | off | Show matches without writing files |
| `--master` | first file | File whose IRIs are preserved; others are rewritten to match |

**Auto-merge rule:** pairs scoring ≥ 95 % are merged without prompting regardless
of `--yes`.

**Modifies files in-place.**  Run on copies if you need to preserve originals, or
use `--dry-run` first.

**Returns:** count of confirmed merges (exit 0).

---

### `cv-audit` — find missing fields

```
cv-audit <FILE.ttl> [--json]
```

Checks `cv:WorkHistory` nodes (employedIn, jobTitle, startDate, endDate,
jobDescription) and `cvx:Project` nodes (projectName, projectDescription, roleTitle,
startDate, activitiesPerformed, benefitsDelivered, at least one usesSkill link).

`--json` emits a JSON array of `{"slug": "...", "field": "...", "question": "..."}`.

---

### `cv-consolidate` — rewrite IRIs using a synonym mapping

```
cv-consolidate <FILE.ttl> (--synonyms <FILE> | --sameas CANONICAL DUP [DUP ...]) [--output OUT.ttl] [--quiet]
```

| Param | Default | Notes |
|-------|---------|-------|
| `FILE.ttl` | — | Input Turtle file to rewrite |
| `--synonyms` / `-s` | — | Turtle file declaring `owl:sameAs` pairs |
| `--sameas` | — | `CANONICAL DUP [DUP ...]` — inline synonym group; repeatable |
| `--output` / `-o` | `<stem>_consolidated.ttl` | Output path; pass input path for in-place rewrite |
| `--quiet` / `-q` | off | Suppress progress output |

At least one of `--synonyms` or `--sameas` is required; both may be combined.

**Inline form (`--sameas`):**

```bash
# First arg = canonical; rest = duplicates merged into it
cv-consolidate cv.ttl --sameas wh_danone_bop_2011 wh_danone_bop_india wh_danone_bop_india_2011

# Multiple groups in one call
cv-consolidate cv.ttl --sameas canonical1 dup1 dup2 --sameas canonical2 dup3
```

Bare slugs (e.g. `wh_danone_bop_2011`) are auto-expanded to `<http://example.org/cv/wh_danone_bop_2011>`.

**Synonyms file form (`--synonyms`):**, subject = old IRI, object = canonical:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix :   <http://example.org/cv/> .

:proj_old    owl:sameAs :proj_canonical .
:company_old owl:sameAs :company_canonical .
```

All triple positions (subject, predicate, object) are rewritten.  Returns a count of affected triples.

**Use case:** known duplicate IRIs within a single TTL.  For cross-file discovery, use `cv-reconcile` instead.

---

### `cv-update` — patch a single field

```
cv-update <FILE.ttl> <slug-or-IRI> <field> <value>
```

Accepted values: any string, `YYYY-MM-DD`, `YYYY-MM`, `YYYY`, or `present`.
Modifies the file in-place.

---

### `cv-to-md` — export TTL to Markdown

```
cv-to-md <FILE.ttl> [--output OUT.md]
```

Produces a structured consultant-style Markdown CV.  Sections with no content are
omitted.  Output order: person header → core skills → professional experience (with
nested projects) → education → certifications & training → MOOCs → personal
projects → publications.

---

### `cv-graph` — render as interactive HTML graph

```
cv-graph <FILE.ttl> [--output OUT.html|OUT.png|OUT.svg]
```

Default output is an interactive HTML file using pyvis.  PNG/SVG require
`networkx` + `matplotlib`.

---

## Python API

```python
from resume_rdf import (
    generate_graph_from_file,   # str|Path → (turtle_str, usage_dict)
    generate_graph_from_bytes,  # bytes, filename → (turtle_str, usage_dict)
    consolidate_ttls,           # list[Path], output_path → MergeStats
    consolidate_synonyms,       # input_ttl, synonyms_ttl → int (triples rewritten)
    load_synonym_map,           # synonyms_ttl → dict[URIRef, URIRef]
    reconcile_interactive,      # list[Path] → int (merges applied)
    ttl_to_markdown,            # str|Path → str
    audit_experience,           # str|Path → list[Question]
    update_field,               # str|Path, slug, field, value → None
    count_triples,              # turtle_str → int
    extract_person_name,        # turtle_str → str|None
    validate_turtle,            # turtle_str → bool
    NAMESPACES,                 # dict[str, str]
    SYSTEM_PROMPT,              # str
)
```

**`generate_graph_from_file(path, *, api_key, extra_context, model, max_tokens)`**
Returns `(turtle_string, usage_dict)`.  Result is cached; safe to call repeatedly.

**`consolidate_ttls(ttl_files, output_file, *, strategy, threshold, master_file, api_key, model, verbose)`**
`master_file` accepts a `str` or `Path`; `None` → first-listed file wins.

**`reconcile_interactive(ttl_files, *, threshold, dry_run, auto_yes, master_file)`**
`auto_yes=True` for batch use.  Returns number of merges applied.

**`consolidate_synonyms(input_file, synonyms_file, output_file=None, *, verbose=False)`**
Rewrites IRIs in `input_file` according to `owl:sameAs` mappings in `synonyms_file`.
Returns count of affected triples.  `output_file` defaults to `<stem>_consolidated.ttl`.

**`load_synonym_map(synonyms_path)`**
Parses a synonyms TTL and returns `{old_IRI: canonical_IRI}`.

**`audit_experience(path)`** returns `list[Question]` where each `Question` has
`.slug`, `.field`, `.question` attributes.

---

## Turtle output structure

All generated graphs use these fixed IRIs for the root nodes:

```turtle
@prefix : <http://example.org/cv/> .

:person a foaf:Person .    # always this IRI
:cv    a cv:CV .           # always this IRI
```

Everything else is slugged from content (`:proj_esg_white_council`,
`:company_northern_energy`, `:skill_python`, etc.).

**Namespaces:**

| Prefix | URI | Purpose |
|--------|-----|---------|
| `cv:` | `http://purl.org/captsolo/resume-rdf/0.2/cv#` | Core ontology |
| `cvx:` | `http://example.org/cv-extension#` | Custom extension |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Person identity |
| `bibo:` | `http://purl.org/ontology/bibo/` | Publications |
| `dcterms:` | `http://purl.org/dc/terms/` | Publication metadata |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals |

**Date types used:**

| Type | Example | When |
|------|---------|------|
| `xsd:date` | `"2024-02-01"^^xsd:date` | Full date known |
| `xsd:gYearMonth` | `"2024-02"^^xsd:gYearMonth` | Year+month only |
| `xsd:gYear` | `"2024"^^xsd:gYear` | Year only |

---

## Recommended pipeline (multi-CV corpus)

```bash
# 1. Parse all CVs (skips any .ttl that already exists)
./process_cvs.sh /path/to/cvs/ --output /path/to/cvs/master.ttl --strategy llm

# Or step-by-step:

# 1. Parse
for f in cvs/*.pdf cvs/*.docx; do
    cv-to-rdf "$f" --context "CV process output MUST BE in English."
done

# 2. Reconcile cross-file IRIs (same-person pairs or shared entities)
cv-reconcile cvs/*.ttl --yes

# 3. Merge same-person CVs
cv-merge cvs/sam_v1.ttl cvs/sam_v2.ttl --output cvs/sam_merged.ttl --strategy llm

# 4. Export and audit
cv-to-md cvs/sam_merged.ttl --output cvs/sam_merged.md
cv-audit cvs/sam_merged.ttl --json
```

---

## Common gotchas

| Situation | What happens | Fix |
|-----------|-------------|-----|
| `ANTHROPIC_API_KEY` not set | `cv-to-rdf` exits with error; `process_cvs.sh` exits early | Export the key or add to `.env` |
| `.doc` file without antiword/catdoc | `RuntimeError` | `apt install antiword` |
| Running `cv-merge` on different-person CVs | IRIs get unified, destroying person identity | Use `cv-reconcile` instead |
| Same input parsed twice | Returns cached result; no API call | Delete `cache/<sha256>.json` to force re-parse |
| Non-English CV without `--context` | Output in original language | Pass `--context "CV process output MUST BE in English."` |
| `--strategy llm` without API key | `ValueError` at merge time | Set `ANTHROPIC_API_KEY` or pass `--api-key` |
| IRI collisions across unreconciled files | SPARQL queries only see one entity | Run `cv-reconcile` before loading into a triplestore |
| `cv-reconcile` modifies files you wanted to keep | Source TTLs rewritten in-place | Copy first, or use `--dry-run` to preview |
| Very long CV (> ~8000 tokens of text) | Truncated output | Pass `--max-tokens 32000` and use a larger model |

---

## Worked example

See `examples/shire_walkthrough.md` for a complete end-to-end walkthrough using the
Shire Consulting team (Sam Gamgee + Frodo Baggins), including TTL snippets,
reconciler session output, merge stats, and example SPARQL queries.
