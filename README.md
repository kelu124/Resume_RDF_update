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

---

## Project structure

```
resume_rdf/                 ← importable Python library
├── __init__.py             public API
├── ontology.py             SYSTEM_PROMPT + namespace constants
├── parsing.py              content builders, Turtle helpers
├── cache.py                file-based SHA-256 response cache
└── api.py                  generate_graph_from_file / _from_bytes

app.py                      Streamlit web app (thin wrapper)
cv_to_knowledge_graph.py    CLI script / cv-to-rdf entry-point (thin wrapper)
pyproject.toml              pip-installable package definition
download_data.py            dataset download helper
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

## CLI

After `pip install .` a `cv-to-rdf` command is available:

```bash
# Basic — writes <cv_stem>.ttl next to the input
cv-to-rdf my_cv.pdf

# Or run the script directly
python cv_to_knowledge_graph.py my_cv.pdf \
  --output graph.ttl \
  --context "Energy and transport sectors, output in English." \
  --model claude-opus-4-6 \
  --max-tokens 60000 \
  --validate \
  --quiet
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

Opens at `http://localhost:8501`. After signing in:

1. Upload your CV (PDF, `.txt`, or `.md`)
2. Optionally add a context note (language preference, main sectors, etc.)
3. Click **Generate knowledge graph**
4. Download the `.ttl` file

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
cv-merge sam_v1.ttl sam_v2.ttl --output sam_merged.ttl
```

Example output:

```
Merged 2 file(s)  (673 input triples)
  IRI mappings applied : 7
  Conflicts resolved   : 12
  Output triples       : 389
  Saved to             : sam_merged.ttl
```

Options:

| Flag | Effect |
|------|--------|
| `--threshold 0.65` | Similarity threshold for entity reconciliation (default: `0.70`) |
| `--output FILE` | Output path (required) |

### Python API

```python
from resume_rdf import consolidate_ttls, MergeStats

stats: MergeStats = consolidate_ttls(
    ["sam_v1.ttl", "sam_v2.ttl"],
    "sam_merged.ttl",
    threshold=0.70,        # optional, default 0.70
)
print(stats.input_triples)      # total triples across all input files
print(stats.iri_mappings)       # entity IRIs unified by reconciliation
print(stats.conflicts_resolved) # literal fields where values differed
print(stats.output_triples)     # triples in merged file
```

### Merge heuristics

For each `(subject, predicate)` pair that has **different values across files**:

| Predicate type | Strategy |
|----------------|----------|
| URI-valued (skills, type links) | **Union** — all values kept |
| Description / title literals | **Longest string** wins |
| `startDate` | **Earliest** date wins |
| `endDate` | **Latest** date wins (`"present"` beats any date) |
| Other string literals | **Longest string** wins |

IRIs are first unified with the same fuzzy-matching logic as `cv-reconcile`
(threshold 0.70 by default, which is lower than the cross-person default of 0.75
to account for same-person CVs using more varied wording for the same entities).

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

The IRI from the **first file listed** is kept as canonical.  Re-order the
arguments to choose which IRI wins.

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
