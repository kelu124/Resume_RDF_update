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

> Parse a CV into a structured [Turtle RDF](https://www.w3.org/TR/turtle/) knowledge graph using the [ResumeRDF ontology](http://rdfs.org/resume-rdf/) — via a password-protected Streamlit web app or a standalone Python script.

---

## Overview

This tool takes a CV (PDF or plain text) and uses the [Anthropic Claude API](https://www.anthropic.com) to extract structured information and serialise it as **Turtle RDF**, ready to load into any SPARQL-capable triplestore (GraphDB, Apache Jena Fuseki, Stardog, Oxigraph, …).

The graph captures not just employment history and skills, but also the **project-level detail** that a standard CV ontology misses: client names, roles, activities performed, benefits delivered, and domain tags — as well as MOOCs, ad-hoc trainings, personal projects, and publications.

After each run, both the original CV and the generated `.ttl` file are **automatically emailed** to a configured recipient.

---

## Ontology

The graph uses a combination of established vocabularies and a lightweight custom extension:

| Prefix | Namespace | Purpose |
|--------|-----------|---------|
| `cv:` | `http://purl.org/captsolo/resume-rdf/0.2/cv#` | ResumeRDF core — person, work history, education, skills |
| `cvb:` | `http://purl.org/captsolo/resume-rdf/0.2/base#` | ResumeRDF base taxonomy |
| `cvx:` | `http://example.org/cv-extension#` | Custom extension — projects, trainings, MOOCs, personal projects |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Person identity |
| `bibo:` | `http://purl.org/ontology/bibo/` | Publications (articles, reports, patents, …) |
| `dcterms:` | `http://purl.org/dc/terms/` | Publication metadata (title, date) |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals (dates, integers) |

### Node types extracted

| RDF Class | Linked via | Description |
|-----------|-----------|-------------|
| `foaf:Person` + `cv:CV` | — | Identity and CV root |
| `cv:WorkHistory` | `cv:hasWorkHistory` | Employment positions |
| `cv:Company` | `cv:employedIn` | Employers and clients |
| `cvx:Project` | `cvx:hasProject` | Client engagements with role, activities, benefits, domain tags |
| `cv:Skill` | `cv:hasSkill` | Technical and professional skills |
| `cv:Education` | `cv:hasEducation` | Formal degrees |
| `cvx:MOOC` | `cvx:hasMOOC` | Online courses (Coursera, edX, Udemy, …) |
| `cvx:Training` | `cvx:hasTraining` | Workshops, certifications, bootcamps |
| `cvx:PersonalProject` | `cvx:hasPersonalProject` | Open-source, hardware, community projects |
| `bibo:AcademicArticle` / `bibo:Report` / … | `cvx:hasPublication` | Papers, reports, patents, articles |

### Project-level detail (`cvx:Project`)

Each professional engagement captures:

```turtle
:proj_example a cvx:Project ;
    cvx:projectName         "Smart Grid Analytics" ;
    cvx:projectDescription  "Digital twin platform for grid monitoring." ;
    cvx:clientName          "National Grid" ;
    cvx:roleTitle           "Technical Lead" ;
    cvx:startDate           "2022-03-01"^^xsd:date ;
    cvx:endDate             "2023-06-30"^^xsd:date ;
    cvx:activitiesPerformed "Designed the data pipeline; led stakeholder workshops." ;
    cvx:benefitsDelivered   "30% reduction in fault detection time." ;
    cvx:domain              "energy" ;
    cvx:domain              "technology" .
```

---

## Project structure

```
.
├── app.py                        # Streamlit web application
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml              # ← create from secrets.toml.example (never commit)
```

---

## Installation

```bash
git clone https://github.com/kelu124/Resume_RDF_update.git
cd Resume_RDF_update
pip install -r requirements.txt
```

**Requirements:**

```
anthropic>=0.28.0
streamlit>=1.35.0
```

> `rdflib` is optional — install it if you want Turtle validation in the CLI script:
> ```bash
> pip install rdflib
> ```

---

## Configuration

Copy the example secrets file and fill in your values:

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

[email]
sender_address      = "your-sender@gmail.com"
sender_app_password = "xxxx xxxx xxxx xxxx"
recipient           = "recipient@example.com"
```

### Getting an Anthropic API key

1. Sign up or log in at [console.anthropic.com](https://console.anthropic.com)
2. Go to **Settings → API Keys** → **Create Key**
3. Copy the `sk-ant-...` key into `secrets.toml`

### Getting a Gmail App Password

The app uses Gmail SMTP to send results by email. A Gmail App Password is required — this is **not** your regular Gmail password.

1. Enable **2-Step Verification** on your Google account: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Go to **App Passwords**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Name it (e.g. *CV Graph App*) and click **Generate**
4. Copy the 16-character code into `secrets.toml` → `sender_app_password`

---

## Usage

### Streamlit web app

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. After signing in:

1. Upload your CV (PDF, `.txt`, or `.md`)
2. Optionally add a context note (language preference, main sectors, etc.)
3. Click **Generate knowledge graph**
4. Download the `.ttl` file — it is also emailed automatically

### CLI script

```bash
# Basic — writes <cv_stem>.ttl next to the input
python cv_to_knowledge_graph.py my_cv.pdf

# Custom output path + context hint
python cv_to_knowledge_graph.py my_cv.pdf \
  --output graph.ttl \
  --context "I work mainly in energy and transport. Output in English."

# Validate the Turtle syntax with rdflib
python cv_to_knowledge_graph.py my_cv.txt --validate

# Use a different model
python cv_to_knowledge_graph.py my_cv.pdf --model claude-opus-4-6
```

The API key can be passed via environment variable (recommended) or flag:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or
python cv_to_knowledge_graph.py my_cv.pdf --api-key sk-ant-...
```

---

## Loading the graph into a triplestore

Once you have a `.ttl` file, load it into your triplestore of choice:

**Apache Jena Fuseki**
```bash
curl -X PUT --data-binary @graph.ttl \
  -H "Content-Type: text/turtle" \
  http://localhost:3030/cv/data
```

**GraphDB** — use the **Import → Upload RDF files** UI, or the REST API.

**Oxigraph** (in-process, Python)
```python
from pyoxigraph import Store
store = Store()
store.load(open("graph.ttl", "rb"), mime_type="text/turtle")
```

You can then query with SPARQL. Example — list all projects tagged with the `energy` domain:

```sparql
PREFIX cvx: <http://example.org/cv-extension#>

SELECT ?name ?client ?role WHERE {
  ?proj a cvx:Project ;
        cvx:domain "energy" ;
        cvx:projectName ?name ;
        cvx:clientName  ?client ;
        cvx:roleTitle   ?role .
}
ORDER BY ?name
```

---

## Notes

- The app uses **streaming** (`client.messages.stream`) for the Anthropic API call, which is required when `max_tokens` is large enough to potentially exceed the 10-minute request window.
- The model used is `claude-sonnet-4-6`. Swap for `claude-opus-4-6` in `app.py` if you need maximum extraction quality on very dense CVs.
- Dates are inferred from context when not explicitly stated; review the output for approximations (year-only dates default to `YYYY-01-01`).
- The `.streamlit/secrets.toml` file is listed in `.gitignore` and must **never** be committed to version control.

---

## License

MIT License — see the header of this file or [choosealicense.com/licenses/mit](https://choosealicense.com/licenses/mit/) for the full text.