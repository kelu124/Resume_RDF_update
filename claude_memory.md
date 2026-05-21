# claude_memory.md
> Persistent notes for AI assistants working in this repository.

## What this repo does

Converts a CV (PDF, `.txt`, or `.md`) into a **Turtle RDF knowledge graph** using the Anthropic Claude API.  Two entry points:

| File | Purpose |
|------|---------|
| `app.py` | Password-protected Streamlit web app with file upload, streaming API call, and Gmail email delivery |
| `cv_to_knowledge_graph.py` | CLI script — same logic, adds `--validate` (rdflib), `--quiet`, `--model`, `--max-tokens` flags |

## Ontology map

| Prefix | Base URI | Role |
|--------|----------|------|
| `cv:` | `http://purl.org/captsolo/resume-rdf/0.2/cv#` | ResumeRDF core: Person, WorkHistory, Company, Skill, Education |
| `cvb:` | `http://purl.org/captsolo/resume-rdf/0.2/base#` | ResumeRDF base taxonomy (currently declared but lightly used) |
| `cvx:` | `http://example.org/cv-extension#` | Custom extension: Project, MOOC, Training, PersonalProject |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Person identity |
| `bibo:` | `http://purl.org/ontology/bibo/` | Publications |
| `dcterms:` | `http://purl.org/dc/terms/` | Publication metadata |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals |

### Key node types and their linking predicates

```
:cv  cv:hasWorkHistory  → cv:WorkHistory
          cvx:hasProject    → cvx:Project       ← no direct Skill link yet (see feat/project-skill-link)
     cv:hasSkill        → cv:Skill
     cv:hasEducation    → cv:Education
     cvx:hasMOOC        → cvx:MOOC
     cvx:hasTraining    → cvx:Training
     cvx:hasPersonalProject → cvx:PersonalProject
     cvx:hasPublication → bibo:*
```

### cvx:Project fields

`projectName`, `projectDescription`, `clientName`, `roleTitle`, `startDate`, `endDate`,
`activitiesPerformed`, `benefitsDelivered`, `domain` (repeatable, controlled vocab).

Allowed `domain` values: `energy`, `transportation`, `finance`, `healthcare`, `industry`,
`telecom`, `public-sector`, `retail`, `technology`, `environment`, `other`.

## Architecture notes

- The SYSTEM_PROMPT (identical in both files) drives all extraction. Any ontology change must be applied **in both files**.
- Streaming (`client.messages.stream`) is used to handle the large `max_tokens` budget (default 60 000).
- Default model: `claude-sonnet-4-6`. Swap for `claude-opus-4-6` for denser CVs.
- Secrets live in `.streamlit/secrets.toml` (gitignored). CLI uses `ANTHROPIC_API_KEY` env var.

## Branch history

| Branch | Change |
|--------|--------|
| `main` | Initial implementation |
| `feat/project-skill-link` | Adds `cvx:usesSkill` predicate linking `cvx:Project` → `cv:Skill` |

## Open gaps / ideas

- `cvb:` namespace is declared but no `cvb:` triples are currently emitted.
- No SHACL or OWL shapes file — validation is limited to Turtle syntax (rdflib).
- A future `cvx:requiresSkill` on `cvx:Project` would allow SPARQL queries like "which projects used Python?".
