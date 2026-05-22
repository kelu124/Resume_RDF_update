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
