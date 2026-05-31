# CV Ontology — Top 5 Improvement Recommendations

These recommendations are based on a review of `resume_rdf/ontology.py`, `resume_rdf/parsing.py`, `resume_rdf/export.py`, `resume_rdf/reconcile.py`, and observed deduplication failures.

---

## 1. Replace the placeholder `cvx` namespace URI

**Current state:** All extensions live under `http://example.org/cv-extension#` — a non-resolvable, non-dereferenceable example URI.

**Problem:** If graphs are ever shared outside the local toolchain (Linked Open Data, SPARQL endpoints, RDF dumps), other consumers will have no way to dereference the namespace for documentation. The string `example.org` also collides conceptually with any other tool that chose the same throwaway URI.

**Recommendation:** Register and own a stable URI such as `https://ontology.<your-domain>/cv-extension/0.1#` and redirect it to a published OWL/RDFS schema. Until a domain is available, at minimum rename it to something clearly internal, e.g. `http://vocab.internal/cv-extension#`, and update `NAMESPACES` in `ontology.py` and all downstream constants in `reconcile.py`.

**Impact on tooling:** Parsing, dedup, and export all use string constants derived from this URI; a single search-and-replace handles the migration.

---

## 2. Use typed partial dates (`xsd:gYear`, `xsd:gYearMonth`)

**Current state:** All date fields are declared `xsd:date` (requiring YYYY-MM-DD), but CVs frequently carry only a year ("2019") or a year-month ("2019-06"). The parser currently emits fake full dates (e.g. `"2019-01-01"^^xsd:date`) or drops the day portion silently.

**Problem:** Fake day-precision inflates apparent certainty. When deduplication compares `"2019-01-01"^^xsd:date` from one CV against `"2019-06-15"^^xsd:date` from another for the same job, they look further apart than they are, penalising the date-overlap score.

**Recommendation:**
- Use `"2019"^^xsd:gYear` when only the year is known.
- Use `"2019-06"^^xsd:gYearMonth` when year and month are known.
- Update `_date_overlap_score` in `reconcile.py` to parse all three XSD date types.
- Update the system prompt in `ontology.py` to instruct the model to choose the most specific type available.

**Impact:** Directly improves dedup accuracy and makes exported Markdown CVs more faithful to source material.

---

## 3. Add a stable employer identifier to `cv:Company` nodes

**Current state:** Company deduplication (both within-graph and cross-file) relies entirely on fuzzy `cv:Name` similarity. "CNRS – Centre National de la Recherche Scientifique" and "CNRS" will score differently depending on which CV's phrasing the model adopted.

**Problem:** Name-based fuzzy matching is fragile for organisations with well-known abbreviations, parent/subsidiary relationships (e.g. "Philips Healthcare" vs "Philips"), or translated names (multinational CVs).

**Recommendation:** Add an optional `cvx:companyLinkedInURL` or `cvx:legalIdentifier` predicate to company nodes and instruct the model to populate it when inferable from context. When two company nodes share the same identifier value, treat them as exact matches in `dedup_companies` regardless of name similarity. This reduces LLM API calls for employer disambiguation and makes cross-CV reconciliation deterministic for well-known organisations.

```turtle
:company_cnrs a cv:Company ;
    cv:Name "CNRS" ;
    cvx:companyLinkedInURL <https://www.linkedin.com/company/cnrs/> ;
    cv:Country "France" .
```

---

## 4. Split `cvx:Training` into `cvx:Training` and `cvx:Certification`

**Current state:** A single `cvx:Training` class carries both ad-hoc training (workshops, bootcamps, short courses) and professional certifications (PMP, AWS Certified, CISSP). The only distinction is the presence of `cvx:certificationName` on some nodes.

**Problem:**
- Deduplication must guess whether a node is a training or a cert to choose the right comparison logic.
- Export (`export.py`) has to check both predicates to decide how to render a node.
- A node can simultaneously have `cvx:trainingTitle` and `cvx:certificationName` with no formal relationship declared.

**Recommendation:** Define a `cvx:Certification` subclass with its own mandatory predicates:

```turtle
cvx:Certification rdfs:subClassOf cvx:Training ;
    rdfs:comment "A credential issued by a certifying body, with an optional ID and expiry." .

:cert_pmp a cvx:Certification ;
    cvx:certificationName     "Project Management Professional (PMP)" ;
    cvx:certificationProvider "Project Management Institute" ;
    cvx:certificationDate     "2021-03-15"^^xsd:date ;
    cvx:certificationID       "12345678" ;
    cvx:certificationExpiry   "2024-03-15"^^xsd:date .
```

Then `cvx:trainingTitle` stays on `cvx:Training` and `cvx:certificationName` becomes the canonical predicate only on `cvx:Certification`. This lets `dedup_training` and `dedup_moocs` check `rdf:type` instead of probing for predicate presence, and lets the exporter render certification cards with expiry warnings.

---

## 5. Consolidate project-to-skill linkage

**Current state:** Two different predicates can link a project to a skill:
- `cvx:usesSkill` — defined in the PROJECTS section of the system prompt, links a `cvx:Project` to a `:skill_SLUG`
- `cv:skill` — a predicate inherited from the base CV ontology, also appears on `cv:WorkHistory` nodes

Both are collected in `_UNION_PREDS` in `reconcile.py` and both propagate through dedup merges, but only `cvx:usesSkill` is used in export and visualisation. The duplication causes silent data loss when dedup unions `cv:skill` triples onto a node and `export.py` then ignores them.

**Recommendation:**
- Deprecate `cv:skill` on `cvx:Project` nodes; remove it from `_UNION_PREDS`.
- Use `cvx:usesSkill` exclusively for project→skill links.
- On `cv:WorkHistory`, use `cv:hasSkill` (already defined in the base ontology) and document the distinction clearly in the system prompt: project nodes use `cvx:usesSkill`, work history nodes use `cv:hasSkill`.
- Add a QA check in `qa.py` that flags any `cv:skill` triple on a project node as a lint warning.

This change eliminates the main source of "ghost" skill triples that survive deduplication but never appear in any CV output.
