# Shire Consulting: a worked walkthrough

This guide walks through the full `resume-rdf` pipeline using the Shire Consulting
team as a realistic example.  The source files are in `shire/`:

| File | Person | Framing |
|------|--------|---------|
| `shire/sam_gamgee_cv1.md` | Sam Gamgee | Chronological — Data Engineering & Analytics |
| `shire/sam_gamgee_cv2.md` | Sam Gamgee | ESG focus — Sustainability & Data Architecture |
| `shire/frodo_baggins_cv.md` | Frodo Baggins | Senior Management Consultant |

Sam and Frodo worked together on three major engagements: the White Council Capital
ESG platform, the Mordor Industrial supply chain programme, and the Northern Energy
smart grid modernisation.  Their CVs will share client company IRIs and — after
cross-file reconciliation — shared project IRIs too, making cross-person SPARQL
queries possible.

---

## Prerequisites

```bash
pip install "resume-rdf[all]"
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Step 1 — Parse each CV to Turtle RDF

Each source file (PDF, DOCX, or Markdown) is converted to a self-contained Turtle
graph.

```bash
cv-to-rdf shire/sam_gamgee_cv1.md \
    --output shire/shire_ttl/sam_v1.ttl \
    --context "CV process output MUST BE in English."

cv-to-rdf shire/sam_gamgee_cv2.md \
    --output shire/shire_ttl/sam_v2.ttl \
    --context "CV process output MUST BE in English."

cv-to-rdf shire/frodo_baggins_cv.md \
    --output shire/shire_ttl/frodo.ttl \
    --context "CV process output MUST BE in English."
```

Each command makes one Claude API call (result is cached, so re-running is free).
Typical output sizes:

| TTL file | Lines |
|----------|-------|
| `sam_v1.ttl` | ~340 |
| `sam_v2.ttl` | ~360 |
| `frodo.ttl`  | ~280 |

### What the parser produces

Both Sam CVs share the same `:person` and `:cv` root nodes (the parser always uses
these fixed IRIs), but slug everything else from the content — so the same employer
or project described slightly differently in two CVs ends up with different IRIs:

```turtle
# sam_v1.ttl — chronological framing
:person a foaf:Person ;
    foaf:name "Sam Gamgee" ;
    foaf:mbox <mailto:sam.gamgee@shire-consulting.co.uk> .

:cv a cv:CV ;
    cv:cvTitle "Data Engineering & Analytics Consultant" ;
    cv:hasWorkHistory :wh_shire_2020, :wh_brandybuck_2017 .

:company_shire_consulting a cv:Company ;
    cv:Name "Shire Consulting Group" ;
    cv:Locality "Leeds" .

:company_white_council a cv:Company ;
    cv:Name "White Council Capital" ;
    cv:Industry "Financial Services" .

:proj_esg_white_council a cvx:Project ;
    cvx:projectName "White Council Capital — ESG Reporting & Analytics Platform" ;
    cvx:roleTitle   "Sustainability Data Analyst & Engineer" ;
    cvx:startDate   "2024-02-01"^^xsd:date ;
    cvx:endDate     "2024-11-30"^^xsd:date ;
    cvx:domain      "finance" .
```

```turtle
# sam_v2.ttl — ESG framing (same project, different IRI and richer ESG context)
:cv a cv:CV ;
    cv:cvTitle "Sustainability Data Consultant | ESG Analytics | Data Architecture" .

:company_white_council_capital a cv:Company ;   # ← different slug
    cv:Name "White Council Capital" .

:proj_esg_platform_wcc_2024 a cvx:Project ;    # ← different slug
    cvx:projectName "ESG Reporting & Analytics Platform — White Council Capital" ;
    cvx:roleTitle   "Sustainability Data Engineer" ;
    cvx:startDate   "2024-02-01"^^xsd:date ;
    cvx:endDate     "2024-11-30"^^xsd:date ;
    cvx:domain      "finance" .
```

The ESG CV also carries a publication not in the chronological one:

```turtle
# sam_v2.ttl only
:pub_odsc_rdf_esg_2025 a bibo:Article ;
    dcterms:title "RDF knowledge graphs for ESG provenance" ;
    cvx:publicationVenue "Open Data Science Conference, Edinburgh" ;
    dcterms:date  "2025-03-01"^^xsd:date .
```

---

## Step 2 — Reconcile Sam's two CVs

Before merging, we need to align the IRIs so that the same real-world entity
(company, project, skill) resolves to the same identifier in both files.

```bash
cv-reconcile shire/shire_ttl/sam_v1.ttl shire/shire_ttl/sam_v2.ttl
```

The reconciler extracts all `cvx:Project` and `cv:Company` entities from both files,
computes pairwise similarity, and surfaces pairs above the 75 % threshold:

```
Loading 2 file(s)…
  Extracted 18 entities (11 projects, 7 companies).

Found 5 candidate pair(s) at ≥75% similarity:

── [1/5]  PROJECT  (similarity 91%) ──
  A: 'White Council Capital — ESG Reporting & Analytics Platform'   :proj_esg_white_council
     (sam_v1.ttl)
  B: 'ESG Reporting & Analytics Platform — White Council Capital'   :proj_esg_platform_wcc_2024
     (sam_v2.ttl)
  Canonical if merged → A  (:proj_esg_white_council)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :proj_esg_platform_wcc_2024  →  :proj_esg_white_council

── [2/5]  PROJECT  (similarity 89%) ──
  A: 'Northern Energy Holdings — Smart Grid Modernisation Programme'  :proj_northern_energy_smartgrid
     (sam_v1.ttl)
  B: 'Smart Grid Modernisation — Northern Energy Holdings'            :proj_smart_grid_neh_2021
     (sam_v2.ttl)
  Canonical if merged → A  (:proj_northern_energy_smartgrid)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :proj_smart_grid_neh_2021  →  :proj_northern_energy_smartgrid

── [3/5]  PROJECT  (similarity 88%) ──
  A: 'Mordor Industrial Group — Supply Chain Resilience Programme'    :proj_mordor_supply_chain
     (sam_v1.ttl)
  B: 'Supply Chain Resilience — Mordor Industrial Group'              :proj_supply_chain_mordor_2022
     (sam_v2.ttl)
  Canonical if merged → A  (:proj_mordor_supply_chain)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :proj_supply_chain_mordor_2022  →  :proj_mordor_supply_chain

── [4/5]  COMPANY  (similarity 84%) ──
  A: 'White Council Capital'   :company_white_council
     (sam_v1.ttl)
  B: 'White Council Capital'   :company_white_council_capital
     (sam_v2.ttl)
  Canonical if merged → A  (:company_white_council)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :company_white_council_capital  →  :company_white_council

── [5/5]  COMPANY  (similarity 79%) ──
  A: 'Rivendell Health Systems'   :company_rivendell_health
     (sam_v1.ttl)
  B: 'Rivendell Health Systems'   :company_rivendell_partners
     (sam_v2.ttl)
  Canonical if merged → A  (:company_rivendell_health)
  Same entity? [y/n/q(uit)] y
  ✓ Will rewrite  :company_rivendell_partners  →  :company_rivendell_health

Applying 5 merge(s) across 2 file(s)…
  sam_v2.ttl: 18 triple(s) rewritten
Done.
```

After this step, `sam_v2.ttl` has been rewritten in-place: every occurrence of
`:proj_esg_platform_wcc_2024` is now `:proj_esg_white_council`, and so on.  The
files are ready to merge without IRI collisions.

> **Tip — use `--master` to pin an IRI set.**  If sam_v1 is your "golden" CV and
> you always want its IRIs to win, pass `--master shire/shire_ttl/sam_v1.ttl`.
> This is useful when a single canonical record already exists and you are importing
> supplementary CVs into it.

> **Tip — batch mode.**  Replace `[y/n/q]` prompts with automatic confirmation by
> adding `--yes`.  Pairs scoring ≥ 95 % are always auto-merged regardless.

---

## Step 3 — Merge Sam's two CVs into one enriched TTL

With IRIs aligned, `cv-merge` loads both files, applies the remaining entity
unification, then resolves conflicts across every `(subject, predicate)` pair where
the two CVs disagree.

```bash
cv-merge shire/shire_ttl/sam_v1.ttl shire/shire_ttl/sam_v2.ttl \
    --output shire/shire_merged/sam_merged.ttl \
    --strategy llm
```

```
Merged 2 file(s)  (702 input triples)
  Strategy             : llm
  IRI mappings applied : 5
  Conflicts resolved   : 14
  LLM API calls        : 9
  LLM cache hits       : 5
  Duplicates removed   : 12
  Output triples       : 389
  Saved to             : shire/shire_merged/sam_merged.ttl
```

### What gets merged

**Skills — union across both CVs.**  The chronological CV lists `:skill_rdf_sparql`;
the ESG CV lists `:skill_rdf_turtle_sparql`.  These are separate nodes (different
slugs), so both appear in the merged graph.  The merged CV therefore has the complete
superset of skills from both framings.

**Project descriptions — synthesised by Claude.**  The two CVs describe the White
Council Capital ESG project from different angles:

*sam_v1 `benefitsDelivered`:*
> Error rate fell from ~12 % to under 0.5 % at first downstream consumption.
> SFDR PAI compute cost reduced by 60 % vs. the incumbent Excel-based process.
> 35 portfolio managers using self-service dashboards from day one of go-live.

*sam_v2 `benefitsDelivered`:*
> Reporting cycle cut from 22 days to 4 days; first SFDR PAI report produced three
> weeks ahead of regulatory deadline; 100 % audit trail coverage vs. 41 % previously.

*Merged (LLM synthesis):*
> Reduced reporting cycle from 22 days to 4 days and delivered the first SFDR PAI
> report three weeks ahead of the regulatory deadline. Error rate at first downstream
> consumption fell from ~12 % to under 0.5 %; SFDR PAI compute cost reduced by 60 %
> vs. the incumbent Excel workbook. Audit trail coverage increased from 41 % to
> 100 %; 35 portfolio managers adopted the self-service Power BI dashboards from
> day one of go-live.

**Dates — earliest startDate, latest endDate.**  If sam_v1 says a project ended
`"2022-06-30"^^xsd:date` and sam_v2 says `"2022-06-01"^^xsd:date`, the merger keeps
`2022-06-30` (latest).

**URI-valued objects — always unioned.**  All `cvx:usesSkill` links from both CVs
are preserved; no skill link is ever silently dropped.

**Publications — only in sam_v2, so carried through intact.**
`:pub_odsc_rdf_esg_2025` (the ODSC Edinburgh talk on RDF for ESG provenance) appears
in the merged output even though sam_v1 never mentioned it.

### Choosing a strategy

| Strategy | When to use |
|----------|-------------|
| `--strategy longest` | Quick pass; preserves the most detail without API calls |
| `--strategy concat` | Zero information loss; output can be verbose |
| `--strategy llm` | Best quality; synthesises complementary descriptions into a single coherent text |

All strategies agree on date resolution, URI union, and non-description fields.

---

## Step 4 — Cross-file reconciliation: Sam's merged CV and Frodo's CV

Sam and Frodo are two different people, so their CVs should not be merged.  But they
worked on the same three client engagements, so a shared skills database — or any
SPARQL query like "who has worked on energy projects?" — needs both TTLs to use the
same IRI for Northern Energy Holdings, Mordor Industrial Group, and the shared
projects.

```bash
cv-reconcile shire/shire_merged/sam_merged.ttl shire/shire_ttl/frodo.ttl
```

### Employer nodes that match automatically

Both the parser and the dedup step tend to produce consistent slugs for well-known
names.  In this case several company IRIs already agree across both TTLs:

| IRI | sam_merged.ttl | frodo.ttl |
|-----|---------------|-----------|
| `:company_shire_consulting` | "Shire Consulting Group" | "Shire Consulting Group" |
| `:company_mordor_industrial` | "Mordor Industrial Group" | "Mordor Industrial Group" |
| `:company_northern_energy` | "Northern Energy Holdings" | "Northern Energy Holdings" |
| `:company_white_council` | "White Council Capital" | "White Council Capital" |

These are already unified — no reconciliation action needed for them.

### Project pairs surfaced by the reconciler

The three shared engagements appear as candidate pairs because the project names are
nearly identical but the IRIs differ (Sam's and Frodo's descriptions came from
different angles):

```
── [1/3]  PROJECT  (similarity 94%) ──
  A: 'White Council Capital — ESG Reporting & Analytics Platform'   :proj_esg_white_council
     (sam_merged.ttl)
  B: 'White Council Capital — ESG Reporting & Analytics Platform'   :proj_wcc_esg_2024
     (frodo.ttl)
  Canonical if merged → A  (:proj_esg_white_council)
  Same entity? [y/n/q(uit)]
```

At 94 % similarity this pair auto-merges (≥ 95 % triggers automatic confirmation;
otherwise the user confirms).  After confirmation, Frodo's `:proj_wcc_esg_2024` is
rewritten to `:proj_esg_white_council` everywhere in `frodo.ttl`.

The same happens for the Mordor and Northern Energy projects.

### What cross-file unification enables

Once all three shared project IRIs are unified, a single SPARQL query can answer
"who worked on the Northern Energy smart grid programme?" across both TTLs:

```sparql
PREFIX cvx: <http://example.org/cv-extension#>
PREFIX cv:  <http://purl.org/captsolo/resume-rdf/0.2/cv#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?name ?role WHERE {
  ?proj cvx:projectName ?pname ;
        cvx:roleTitle   ?role .
  FILTER(CONTAINS(?pname, "Northern Energy"))
  ?wh cvx:hasProject ?proj .
  ?cv cv:hasWorkHistory ?wh ;
      cv:aboutPerson    ?p .
  ?p foaf:name ?name .
}
```

| name | role |
|------|------|
| Sam Gamgee | Data Engineering Lead |
| Frodo Baggins | Programme Lead / Technical Architect |

Without IRI unification, the two project nodes would be invisible to each other and
the query would return only the file whose IRI matched the `FILTER`.

### When NOT to merge project pairs

If Sam and Frodo's project nodes describe meaningfully different scopes — e.g.
Sam's Gondor Municipal Authority project (no Frodo involvement) vs. a similarly
named project in another person's CV — answer `n` at the prompt.  The reconciler
never auto-merges below 95 %; every borderline pair comes to you for a decision.

---

## Step 5 — Export to Markdown

```bash
cv-to-md shire/shire_merged/sam_merged.ttl \
    --output shire/shire_merged/sam_merged_cv.md
```

The exporter walks the graph and produces a structured consultant CV:

```markdown
# Sam Gamgee
**Sustainability Data Consultant | ESG Analytics | Data Architecture**

sam.gamgee@shire-consulting.co.uk | +44 7700 900 222 | https://github.com/samgamgee

---

## Core Skills

- Python (pandas, PySpark, dbt, FastAPI)  *(Expert, 8 yr)*
- PySpark / Apache Spark                  *(Advanced, 6 yr)*
- RDF/Turtle, SPARQL, rdflib              *(Advanced, 5 yr)*
- Knowledge Graph Design                  *(Expert, 6 yr)*
- ESG Data Modelling (SFDR, GRI, TCFD)   *(Advanced, 2 yr)*
- SFDR / PAI Indicators                   *(Expert, 4 yr)*
- Apache Kafka                            *(Advanced, 5 yr)*
...

## Professional Experience

### Shire Consulting Group
*Leeds | IT Consulting / Data Engineering | March 2020 – present*

#### White Council Capital — ESG Reporting & Analytics Platform
*Finance | February 2024 – November 2024*
**Role:** Sustainability Data Analyst & Engineer

Delivery of a regulatory-grade ESG reporting and analytics platform…

**Activities:**
Designed the canonical ESG data model covering 500+ indicators aligned to SFDR,
GRI, and TCFD schemas, including a Turtle RDF knowledge graph layer for provenance
tracking. Built ingestion pipelines for nine data sources…

**Outcomes:**
Reduced reporting cycle from 22 days to 4 days and delivered the first SFDR PAI
report three weeks ahead of the regulatory deadline…

**Skills used:** Python · Apache Airflow · PySpark · AWS · RDF/Turtle,SPARQL ·
ESG Data Modelling · Power BI · Data Modelling & FAIR Data Principles
```

The merged CV is richer than either source CV: it includes the publication from the
ESG-framing CV, the full skill set from both framings, and synthesised project
descriptions that capture the complementary detail from each version.

---

## Step 6 — QA audit

```bash
cv-audit shire/shire_merged/sam_merged.ttl
```

```
Found 2 question(s):

  [wh_shire_2020]  endDate
    When did you leave Shire Consulting Group, or is this your current role
    (YYYY-MM-DD or 'present')?

  [wh_rivendell_health_2025]  endDate
    When did you leave Rivendell Health Systems, or is this your current role
    (YYYY-MM-DD or 'present')?
```

Both are ongoing roles — fix them with `cv-update`:

```bash
cv-update shire/shire_merged/sam_merged.ttl wh_shire_2020 endDate present
cv-update shire/shire_merged/sam_merged.ttl wh_rivendell_health_2025 endDate present
```

For Frodo's CV:

```bash
cv-audit shire/shire_ttl/frodo.ttl
```

```
Found 2 question(s):

  [wh_shire_2020]  endDate
    When did you leave Shire Consulting Group, or is this your current role
    (YYYY-MM-DD or 'present')?

  [wh_pelennor_infra_2025]  endDate
    When did you leave Pelennor Infrastructure Partners, or is this your current role
    (YYYY-MM-DD or 'present')?
```

```bash
cv-update shire/shire_ttl/frodo.ttl wh_shire_2020 endDate present
cv-update shire/shire_ttl/frodo.ttl wh_pelennor_infra_2025 endDate present
```

---

## Full pipeline with `process_cvs.sh`

For a folder of CVs, the shell script runs every step automatically:

```bash
./process_cvs.sh shire/ \
    --output shire/master_cv.ttl \
    --strategy llm \
    --context "Shire Consulting Group, UK-based consultancy"
```

The script:
1. Parses each `.md` / `.pdf` / `.docx` file to a `.ttl` sidecar (skips any file
   whose `.ttl` already exists).
2. Runs `cv-reconcile` across all generated TTLs (--yes for batch mode).
3. Runs `cv-merge` to consolidate into `master_cv.ttl`.
4. Runs `cv-to-md` to produce `master_cv.md`.
5. Runs `cv-audit` to list missing fields.

---

## SPARQL queries on the combined graph

Load both reconciled TTLs into a triplestore or in-process store:

```python
from rdflib import ConjunctiveGraph

g = ConjunctiveGraph()
g.parse("shire/shire_merged/sam_merged.ttl", format="turtle")
g.parse("shire/shire_ttl/frodo.ttl",         format="turtle")
```

**Who has energy-sector project experience?**

```sparql
PREFIX cvx: <http://example.org/cv-extension#>
PREFIX cv:  <http://purl.org/captsolo/resume-rdf/0.2/cv#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT DISTINCT ?name ?projName ?role WHERE {
  ?proj a cvx:Project ;
        cvx:domain    "energy" ;
        cvx:projectName ?projName ;
        cvx:roleTitle   ?role .
  ?wh  cvx:hasProject ?proj .
  ?cv  cv:hasWorkHistory ?wh ;
       cv:aboutPerson    ?p .
  ?p   foaf:name ?name .
}
ORDER BY ?name
```

| name | projName | role |
|------|----------|------|
| Frodo Baggins | Northern Energy Holdings — Smart Grid… | Programme Lead / Technical Architect |
| Sam Gamgee | Northern Energy Holdings — Smart Grid… | Data Engineering Lead |

**Which skills appear on SFDR/ESG projects?**

```sparql
PREFIX cvx: <http://example.org/cv-extension#>
PREFIX cv:  <http://purl.org/captsolo/resume-rdf/0.2/cv#>

SELECT DISTINCT ?skillName WHERE {
  ?proj a cvx:Project ;
        cvx:domain     "finance" ;
        cvx:usesSkill  ?skill .
  ?skill cv:skillName ?skillName .
}
```
