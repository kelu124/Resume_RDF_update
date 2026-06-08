<!--
MIT License

Copyright (c) 2025 Luc Jonveaux

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

# 🕸️ CV → RDF Knowledge Graph

> Parse a CV into a structured [Turtle RDF](https://www.w3.org/TR/turtle/) knowledge graph using the [ResumeRDF ontology](http://rdfs.org/resume-rdf/) — as a **Python library**, a CLI tool, or a Streamlit web app.

---

## Overview

This project converts a CV (PDF or plain text) into **Turtle RDF** using the [Anthropic Claude API](https://www.anthropic.com). The core logic lives in the `resume_rdf` Python package, which can be installed and imported independently of the web app or CLI.

The graph captures not just employment history and skills, but also **project-level detail**: client names, roles, activities, benefits, and domain tags — plus MOOCs, certifications, personal projects, and publications.

> **LLM / agent users:** see [`LLM.md`](LLM.md) for a concise guide covering all CLIs, the Python API, pipeline orchestration, output structure, and common gotchas.

---

## Who is this for?

### For the lay person

Think of this tool as a smart reading assistant for CVs. You give it a CV — any format — and it reads through the whole document and extracts every meaningful piece of information: where the person worked, what they did there, which projects they led, what skills they used, and what results they delivered. It then stores all of that in a structured format that a computer can search, compare, and reason over.

The practical result: instead of a PDF that only a human can read, you get a living, queryable profile. You can ask questions like "who has worked on renewable energy projects?" or "which of our people have led teams of more than ten?" and get instant, accurate answers — across dozens or hundreds of CVs at once. The tool also flags gaps ("this role has no end date"), lets you fill them in through a simple chat interface, and can export a clean, formatted CV back out when you need it.

No coding required to use the web app. No data leaves your environment unless you choose to share it.

### For resource managers in consulting firms

Consulting firms live and die by the quality and speed of their staffing decisions. This tool was built with that pressure in mind.

**The problem it solves:** consultant CVs are usually Word documents or PDFs — unstructured, inconsistently formatted, and impossible to query at scale. Finding the right person for a bid means emailing around, relying on memory, or maintaining a spreadsheet that's always out of date.

**What it gives you instead:**

- **A structured, searchable profile for every consultant** — skills, clients, sectors, project roles, certifications, and outcomes, all extracted automatically from existing CVs.
- **Cross-portfolio search** — instantly identify who has relevant experience for a specific client, sector, or technology, without reading a single document.
- **Automatic gap detection** — the tool flags missing information (no project description, no end date, no stated outcomes) and lets you fill those gaps through a conversational interface.
- **CV consolidation** — when a consultant has multiple CV versions for different audiences, the tool merges them into one complete profile without losing any information.
- **Consistent exports** — generate clean, standardised Markdown CVs from any profile, ready to tailor for a bid or framework submission.

The result is a skills database that builds itself from documents you already have, stays up to date as consultants update their CVs, and gives your BD and staffing teams a genuine search capability across the whole bench.

---

## Project structure

```
resume_rdf/                 ← importable Python library
├── __init__.py             public API — re-exports all key symbols
├── api.py                  generate_graph_from_file / _from_bytes
├── cache.py                file-based SHA-256 response cache
├── cli.py                  cv-to-rdf entry-point
├── data.py                 dataset download + iteration helpers
├── export.py               ttl_to_markdown  /  cv-to-md CLI
├── merge.py                consolidate_ttls  /  cv-merge CLI
├── ontology.py             SYSTEM_PROMPT + namespace constants
├── parsing.py              Turtle helpers (count_triples, extract_person_name …)
├── qa.py                   audit_experience, update_field  /  cv-audit, cv-update CLIs
├── reconcile.py            entity reconciliation  /  cv-reconcile CLI
└── viz.py                  visualize_cv  /  cv-graph CLI

app.py                      Streamlit web app (thin wrapper)
application_example.py      standalone end-to-end demo script
pyproject.toml              pip-installable package definition
data/                       master_resumes.jsonl (1 866 records, MIT)
```

---

## Installation

### As a library

```bash
pip install .
# With optional extras:
pip install ".[app]"        # adds streamlit
pip install ".[validate]"   # adds rdflib for Turtle validation
pip install ".[dataset]"    # adds datasets + huggingface_hub
pip install ".[all]"        # everything
```

### From source (dev)

```bash
git clone https://github.com/kelu124/Resume_RDF_update.git
cd Resume_RDF_update
pip install -e ".[all]"
```

---

## Library usage

```python
from resume_rdf import generate_graph_from_file, generate_graph_from_bytes

# From a file path (CLI / batch use)
turtle, usage = generate_graph_from_file(
    "my_cv.pdf",
    api_key="sk-ant-...",                 # or set ANTHROPIC_API_KEY
    extra_context="Energy sector, English labels.",
    model="claude-sonnet-4-6",            # default
)
print(turtle)                             # valid Turtle RDF

# From bytes (web / in-memory use)
with open("my_cv.pdf", "rb") as f:
    turtle, usage = generate_graph_from_bytes(
        f.read(), "my_cv.pdf", api_key="sk-ant-..."
    )

print(f"~{usage['output_tokens']:,} output tokens")
```

### Utilities

```python
from resume_rdf import count_triples, extract_person_name, validate_turtle

print(count_triples(turtle))       # ~420
print(extract_person_name(turtle)) # "Jane Smith"
validate_turtle(turtle)            # True (requires rdflib)
```

### Ontology constants

```python
from resume_rdf import NAMESPACES, SYSTEM_PROMPT

# NAMESPACES is a dict: {"cv": "http://...", "cvx": "http://...", ...}
for prefix, uri in NAMESPACES.items():
    print(f"@prefix {prefix}: <{uri}> .")
```

### Caching

Responses are cached in `cache/<sha256>.json` keyed on the (system prompt,
model, user content) triple.  Delete any `.json` file to bust the cache for
a specific input, or set `LLM_CACHE_DIR` to override the cache directory.

---

## CLI reference

After `pip install .` seven CLI commands are available:

| Command | Extra needed | What it does |
|---------|-------------|--------------|
| `cv-to-rdf` | _(core)_ | Parse a CV file into Turtle RDF |
| `cv-audit` | `[qa]` | Report missing / empty fields in a TTL |
| `cv-update` | `[qa]` | Patch a single field value in a TTL |
| `cv-reconcile` | `[reconcile]` | Unify near-duplicate IRIs across multiple TTLs |
| `cv-merge` | `[merge]` | Merge same-person TTLs into one enriched file |
| `cv-graph` | `[viz]` | Render a TTL as an interactive HTML graph |
| `cv-to-md` | `[export]` | Convert a TTL back to readable Markdown |

### `cv-to-rdf` — parse a CV

```bash
cv-to-rdf my_cv.pdf                              # → my_cv.ttl
cv-to-rdf my_cv.pdf --output graph.ttl
cv-to-rdf my_cv.pdf --context "Energy sector, output in English."
cv-to-rdf my_cv.pdf --model claude-opus-4-7 --max-tokens 80000
cv-to-rdf my_cv.pdf --validate --quiet
```

The API key can be passed via environment variable (recommended) or flag:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or
cv-to-rdf my_cv.pdf --api-key sk-ant-...
```

---

## Streamlit web app

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Four-step pipeline:

| Step | What happens |
|------|-------------|
| **1 · Upload** | Upload `.pdf`, `.txt`, `.md`, `.ttl`, or `.docx` files (multiple). TTL files are used as-is; others are parsed via Claude. Download a ZIP of all parsed TTLs. |
| **2 · Consolidate** | *(only if >1 TTL)* Merge same-person CVs into one enriched graph. Choose strategy: `longest` / `concat` / `llm`. Shows merge stats and lets you download the merged TTL. |
| **3 · QA Chat** | Audit the TTL for missing fields. Questions are asked one at a time in a chat interface; answers are applied in-place via `update_field`. Type `done` or click **Proceed to export** to skip remaining questions. |
| **4 · Export** | Generate Markdown CV, interactive HTML graph, and a ZIP package (TTL + Markdown + HTML). Preview both outputs in the browser. |

### Configuration

```bash
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
[app]
password = "your-app-password"

[anthropic]
api_key = "sk-ant-..."
```

---

## Ontology

The graph combines established vocabularies with a lightweight custom extension:

| Prefix | Namespace | Purpose |
|--------|-----------|---------|
| `cv:` | `http://purl.org/captsolo/resume-rdf/0.2/cv#` | ResumeRDF core |
| `cvb:` | `http://purl.org/captsolo/resume-rdf/0.2/base#` | ResumeRDF base taxonomy |
| `cvx:` | `http://example.org/cv-extension#` | Custom extension |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Person identity |
| `bibo:` | `http://purl.org/ontology/bibo/` | Publications |
| `dcterms:` | `http://purl.org/dc/terms/` | Publication metadata |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals |

### Node types

| RDF Class | Linked via | Description |
|-----------|-----------|-------------|
| `foaf:Person` + `cv:CV` | — | Identity and CV root |
| `cv:WorkHistory` | `cv:hasWorkHistory` | Employment positions |
| `cv:Company` | `cv:employedIn` | Employers and clients |
| `cvx:Project` | `cvx:hasProject` | Client engagements |
| `cv:Skill` | `cv:hasSkill` | Technical and professional skills |
| `cv:Education` | `cv:hasEducation` | Formal degrees |
| `cvx:MOOC` | `cvx:hasMOOC` | Online courses |
| `cvx:Training` | `cvx:hasTraining` | Workshops, certifications |
| `cvx:PersonalProject` | `cvx:hasPersonalProject` | Open-source, hardware, community projects |
| `bibo:AcademicArticle` / … | `cvx:hasPublication` | Papers, reports, patents |

Projects also carry `cvx:usesSkill` links to the `cv:Skill` nodes used on that engagement.

---

## Graph visualisation

Render a Turtle CV as a visual knowledge graph.

Requires `pyvis` (HTML) or `networkx` + `matplotlib` (PNG/SVG):
`pip install "resume-rdf[viz]"`.

### CLI

```bash
cv-graph my_cv.ttl                      # → my_cv.html  (interactive, default)
cv-graph my_cv.ttl --output graph.png   # → static PNG
cv-graph my_cv.ttl --output graph.svg   # → static SVG
```

### Python API

```python
from resume_rdf import visualize_cv

out = visualize_cv("my_cv.ttl")               # → my_cv.html
out = visualize_cv("my_cv.ttl", "graph.png")  # → graph.png
print(f"Saved: {out}")
```

The graph shows: **Person → Employer → Project → Skill**, plus Education,
Training/MOOCs, Personal Projects, and Publications radiating from the person
node.  Hover over any node for the full tooltip (name, role, dates, description).

Node colours:

| Colour | Node type |
|--------|-----------|
| Blue star | Person |
| Orange | Employer (cv:Company) |
| Green diamond | Project (cvx:Project) |
| Brown | Skill (from cvx:usesSkill links) |
| Yellow | Education |
| Grey | Training / Certification |
| Teal | Online course (MOOC) |
| Red diamond | Personal project |
| Purple | Publication |

---

## TTL → Markdown export

Convert a Turtle RDF CV back to clean, human-readable Markdown.

Requires `rdflib`: `pip install "resume-rdf[export]"`.

### CLI

```bash
cv-to-md my_cv.ttl                   # print to stdout
cv-to-md my_cv.ttl --output cv.md    # write to file
```

### Python API

```python
from resume_rdf import ttl_to_markdown

md = ttl_to_markdown("my_cv.ttl")
print(md)

from pathlib import Path
Path("my_cv.md").write_text(ttl_to_markdown("my_cv.ttl"))
```

The output mirrors the structure of a hand-written consultant CV:
person header, core skills, professional experience with nested projects
(activities + outcomes + skills used), education, certifications & training,
personal projects, and publications.  Sections with no content are omitted.

---

## CV quality audit & field update

After generating a graph you can audit it for gaps and fill them in
programmatically.

Requires `rdflib`: `pip install "resume-rdf[qa]"`.

### `cv-audit` — find missing fields

```bash
cv-audit my_cv.ttl
```

Example output:

```
Found 3 question(s):

  [wh_acme_2019]  endDate
    When did you leave Acme Corp, or is this your current role (YYYY-MM-DD or 'present')?

  [proj_smartgrid_2022]  benefitsDelivered
    What outcomes or benefits did project 'Smart Grid Analytics' deliver?

  [proj_smartgrid_2022]  usesSkill
    Which skills were used on project 'Smart Grid Analytics'? (provide skill slugs or names)
```

Add `--json` for machine-readable output:

```bash
cv-audit my_cv.ttl --json
# → [{"slug": "wh_acme_2019", "field": "endDate", "question": "..."}, ...]
```

Fields checked on **`cv:WorkHistory`** nodes: `employedIn`, `jobTitle`,
`startDate`, `endDate`, `jobDescription`.

Fields checked on **`cvx:Project`** nodes: `projectName`, `projectDescription`,
`roleTitle`, `startDate`, `activitiesPerformed`, `benefitsDelivered`,
`usesSkill` (at least one link).

### `cv-update` — patch a single field

```bash
cv-update my_cv.ttl wh_acme_2019 jobTitle "Senior Engineer"
cv-update my_cv.ttl wh_acme_2019 endDate 2023-06-30
cv-update my_cv.ttl proj_smartgrid_2022 benefitsDelivered "Reduced grid losses by 12 %"
```

Accepts a **slug** (local IRI name, e.g. `wh_acme_2019`) or a **full IRI**.
The file is updated in-place.

Supported field names: `jobTitle`, `startDate`, `endDate`, `jobDescription`,
`Name`, `projectName`, `projectDescription`, `clientName`, `roleTitle`,
`activitiesPerformed`, `benefitsDelivered`, `domain`, `skillName`,
`skillLevel`, `skillYearsExperience`, `degreeType`, `eduMajor`,
`courseTitle`, `trainingTitle`, `title`, `date`, `doi`, `name`, and more.
Run `cv-update --help` for the full list.

### Python API

```python
from resume_rdf import audit_experience, update_field, Question

# Audit
questions: list[Question] = audit_experience("my_cv.ttl")
for q in questions:
    print(f"[{q.slug}]  {q.field}: {q.question}")

# Update
update_field("my_cv.ttl", "wh_acme_2019", "jobTitle", "Senior Engineer")
update_field("my_cv.ttl", "proj_smartgrid_2022", "startDate", "2021-03-01")
```

`Question` is a frozen dataclass with three fields: `slug`, `field`, `question`.

---

## TTL consolidation (same-person merge)

When the same person has produced multiple CVs with different framings (chronological,
ESG focus, technical focus …), you can merge them into one richer, deduplicated TTL.

Requires `rdflib`: `pip install "resume-rdf[merge]"`.

### CLI

```bash
# Keep the longest description (default)
cv-merge sam_v1.ttl sam_v2.ttl --output sam_merged.ttl

# Concatenate all unique descriptions with " | "
cv-merge sam_v1.ttl sam_v2.ttl --output sam_merged.ttl --strategy concat

# Ask Claude to synthesise one coherent description (cached)
cv-merge sam_v1.ttl sam_v2.ttl --output sam_merged.ttl --strategy llm
```

Example output:

```
Merged 2 file(s)  (673 input triples)
  Strategy             : llm
  IRI mappings applied : 7
  Conflicts resolved   : 12
  LLM API calls        : 8
  LLM cache hits       : 4
  Output triples       : 389
  Saved to             : sam_merged.ttl
```

Options:

| Flag | Default | Effect |
|------|---------|--------|
| `--strategy` | `longest` | `longest` \| `concat` \| `llm` — see below |
| `--threshold` | `0.70` | Similarity threshold for entity reconciliation |
| `--output FILE` | — | Output path (required) |
| `--master FILE` | first file listed | Treat this file's IRIs as canonical during reconciliation |
| `--api-key KEY` | `$ANTHROPIC_API_KEY` | Required for `--strategy llm` |
| `--model MODEL` | `claude-haiku-4-5-20251001` | Claude model for LLM synthesis |

### Python API

```python
from resume_rdf import consolidate_ttls, MergeStats

# Default: longest string wins
stats = consolidate_ttls(["sam_v1.ttl", "sam_v2.ttl"], "sam_merged.ttl")

# Concatenate (no information loss)
stats = consolidate_ttls(
    ["sam_v1.ttl", "sam_v2.ttl"], "sam_concat.ttl",
    strategy="concat",
)

# LLM synthesis (uses cache — repeated calls are free)
stats = consolidate_ttls(
    ["sam_v1.ttl", "sam_v2.ttl"], "sam_llm.ttl",
    strategy="llm",
    api_key="sk-ant-...",          # or set ANTHROPIC_API_KEY
)

# Pin a master file — its IRIs are kept as canonical during reconciliation
stats = consolidate_ttls(
    ["sam_v1.ttl", "sam_v2.ttl"], "sam_merged.ttl",
    master_file="sam_v1.ttl",
)

print(stats.input_triples)      # total triples across all input files
print(stats.iri_mappings)       # entity IRIs unified by reconciliation
print(stats.conflicts_resolved) # literal fields where values differed
print(stats.output_triples)     # triples in merged file
print(stats.llm_calls)          # Anthropic API calls made (llm strategy)
print(stats.llm_cache_hits)     # calls served from cache (llm strategy)
```

### Merge strategy details

IRIs are first unified with the same fuzzy-matching logic as `cv-reconcile`
(threshold 0.70 by default).  Then, for each `(subject, predicate)` pair with
conflicting values across files:

| Predicate type | All strategies |
|----------------|---------------|
| URI-valued (skills, type links) | **Union** — all values always kept |
| `startDate` | **Earliest** date always wins |
| `endDate` | `"present"` beats any date; otherwise **latest** |
| Other typed literals | **Longest** always wins |

| Predicate type | `longest` | `concat` | `llm` |
|----------------|-----------|----------|-------|
| Description / title fields | longest string | join with `" \| "` | Claude synthesises one coherent text |

The `llm` strategy only calls the API for **description-type predicates**
(`projectDescription`, `jobDescription`, `benefitsDelivered`,
`activitiesPerformed`, `roleTitle`, `projectName`, `jobTitle`).
Results are cached under `cache/merge_<sha256>.json` alongside the CV
parser cache — re-running the same merge is free.

---

## Entity reconciliation

When you have TTL files from multiple CVs and want to query them together via
SPARQL, project names and employer IRIs will often differ slightly across files
(`"Smart Grid Analytics"` vs `"Smart-Grid Analytics"`).  The reconciler finds
these near-duplicates and rewrites the TTL files to share a single canonical IRI.

Requires `rdflib`: `pip install "resume-rdf[reconcile]"`.

### CLI

```bash
cv-reconcile alice.ttl bob.ttl carol.ttl
```

Example session:

```
Loading 2 file(s)…
  Extracted 14 entities (9 projects, 5 companies).

Found 2 candidate pair(s) at ≥75% similarity:

── [1/2]  PROJECT  (similarity 88%) ──
  A: 'Smart Grid Analytics'              :proj_smartgrid_2022
     (alice.ttl)
  B: 'Smart-Grid Analytics'              :proj_smart_grid_analytics
     (bob.ttl)
  Canonical if merged → A  (:proj_smartgrid_2022)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :proj_smart_grid_analytics  →  :proj_smartgrid_2022

── [2/2]  COMPANY  (similarity 82%) ──
  A: 'Acme Corp'                         :company_acme
     (alice.ttl)
  B: 'ACME Corporation'                  :company_acme_corp
     (bob.ttl)
  Canonical if merged → A  (:company_acme)
  Same entity? [y/n/q(uit)] n

Applying 1 merge(s) across 2 file(s)…
  bob.ttl: 4 triple(s) rewritten
Done.
```

Options:

| Flag | Effect |
|------|--------|
| `--threshold 0.80` | Raise bar to reduce false positives (default: `0.75`) |
| `--dry-run` / `-n` | Show matches without writing any files |
| `--yes` / `-y`     | Accept all matches above threshold automatically |
| `--master FILE`    | Treat this file's IRIs as canonical (default: first file listed) |

By default, the IRI from the **first file listed** is kept as canonical.
Use `--master` to pin a specific file regardless of argument order:

```bash
cv-reconcile alice.ttl bob.ttl carol.ttl --master alice.ttl
```

### Python API

```python
from pathlib import Path
from resume_rdf import reconcile_interactive, load_entities, find_matches

# Inspect candidates programmatically
entities = load_entities([Path("alice.ttl"), Path("bob.ttl")])
matches  = find_matches(entities, threshold=0.80)
for m in matches:
    print(f"{m.score:.0%}  {m.a.label!r} ({m.a.source.name}) "
          f"↔  {m.b.label!r} ({m.b.source.name})")

# Interactive merge
n = reconcile_interactive(
    [Path("alice.ttl"), Path("bob.ttl")],
    threshold=0.75,
    dry_run=False,
)
print(f"{n} merge(s) applied")

# Batch/automated mode (no prompts)
n = reconcile_interactive(
    [Path("alice.ttl"), Path("bob.ttl")],
    threshold=0.90,   # high threshold → only near-identical matches
    auto_yes=True,
)

# Pin a master file — its IRIs are always kept as canonical
n = reconcile_interactive(
    [Path("alice.ttl"), Path("bob.ttl")],
    auto_yes=True,
    master_file=Path("alice.ttl"),
)
```

---

## Loading into a triplestore

```bash
# Apache Jena Fuseki
curl -X PUT --data-binary @graph.ttl \
  -H "Content-Type: text/turtle" \
  http://localhost:3030/cv/data
```

```python
# Oxigraph (in-process)
from pyoxigraph import Store
store = Store()
store.load(open("graph.ttl", "rb"), mime_type="text/turtle")
```

```sparql
-- SPARQL: projects that used Python
PREFIX cvx: <http://example.org/cv-extension#>
PREFIX cv:  <http://purl.org/captsolo/resume-rdf/0.2/cv#>

SELECT ?projName ?client WHERE {
  ?proj a cvx:Project ;
        cvx:projectName ?projName ;
        cvx:clientName  ?client ;
        cvx:usesSkill   ?skill .
  ?skill cv:skillName "Python" .
}
```

---

## Resume dataset

`data/master_resumes.jsonl` contains 1 866 real and synthetic résumés from
[datasetmaster/resumes](https://huggingface.co/datasets/datasetmaster/resumes)
(HuggingFace, MIT licence).

### Download

```python
from resume_rdf import download_dataset

path = download_dataset()           # skips download if file already present
path = download_dataset(force=True) # re-download unconditionally
path = download_dataset("/tmp/data") # custom destination directory
```

Or from the command line:

```bash
python download_data.py
```

### Load records

```python
from resume_rdf import load_records, iter_records

# Load all records into a list (1 866 dicts)
records = load_records()
print(len(records))            # 1866
print(records[0].keys())
# dict_keys(['personal_info', 'experience', 'education', 'skills',
#            'projects', 'certifications', 'languages', 'metadata'])

# Memory-efficient iteration (no full file load)
for record in iter_records():
    name   = record["personal_info"]["name"]
    skills = [s.get("name") for s in record.get("skills", [])]
    print(name, "→", skills)
```

Both functions accept a `dest_dir` argument and will auto-download the file
on first use if it is missing (pass `auto_download=False` to suppress this).

---

## License

MIT — see the header of this file or [choosealicense.com/licenses/mit](https://choosealicense.com/licenses/mit/).
