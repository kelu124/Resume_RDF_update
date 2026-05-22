"""
resume_rdf.qa
=============
CV quality-audit and field-update utilities.

``audit_experience(ttl_file)`` loads a Turtle file and returns a list of
:class:`Question` objects for every required field that is absent or blank on
``cv:WorkHistory`` and ``cvx:Project`` nodes.

``update_field(ttl_file, slug_or_iri, field, value)`` resolves a node by slug
or full IRI, sets the named field to the given value, and saves the file
in-place.

Requires
--------
``rdflib >= 6.0``  (``pip install rdflib`` or ``pip install "resume-rdf[validate]"``)

CLI usage
---------
::

    # Print all questions for missing fields
    cv-audit my_cv.ttl

    # Update a single field
    cv-update my_cv.ttl wh_acme_2019 jobTitle "Senior Engineer"
    cv-update my_cv.ttl proj_smartgrid_2022 startDate 2021-03-01

Library usage
-------------
::

    from resume_rdf.qa import audit_experience, update_field

    questions = audit_experience("my_cv.ttl")
    for q in questions:
        print(f"[{q.slug}] {q.field}: {q.question}")

    update_field("my_cv.ttl", "wh_acme_2019", "jobTitle", "Senior Engineer")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from rdflib import Graph, Namespace, URIRef, Literal, RDF
    from rdflib.namespace import XSD
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "resume_rdf.qa requires rdflib.\n"
        "Install it with:  pip install rdflib\n"
        "or:               pip install \"resume-rdf[validate]\""
    ) from _e

_CV   = Namespace("http://purl.org/captsolo/resume-rdf/0.2/cv#")
_CVX  = Namespace("http://example.org/cv-extension#")
_FOAF = Namespace("http://xmlns.com/foaf/0.1/")
_DCTERMS = Namespace("http://purl.org/dc/terms/")
_BIBO    = Namespace("http://purl.org/ontology/bibo/")
_BASE    = "http://example.org/cv/"


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Question:
    """A missing-field question surfaced by :func:`audit_experience`.

    Attributes:
        slug:     Local IRI slug identifying the node (e.g. ``wh_acme_2019``).
        field:    Predicate local name that is missing or empty (e.g. ``jobTitle``).
        question: Human-readable prompt to present to the CV owner.
    """
    slug:     str
    field:    str
    question: str


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _slug_of(iri: URIRef) -> str:
    s = str(iri)
    for sep in ("#", "/"):
        idx = s.rfind(sep)
        if idx >= 0:
            return s[idx + 1:]
    return s


def _get_one(g: Graph, subject, predicate) -> str | None:
    for _, _, obj in g.triples((subject, predicate, None)):
        v = str(obj).strip()
        return v if v else None
    return None


def _has_any(g: Graph, subject, predicate) -> bool:
    return any(True for _ in g.triples((subject, predicate, None)))


# ─────────────────────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────────────────────

def audit_experience(ttl_file: str | Path) -> list[Question]:
    """Audit WorkHistory and Project nodes for missing or empty fields.

    Loads the Turtle file and inspects every ``cv:WorkHistory`` and every
    ``cvx:Project`` linked from a WorkHistory.  Returns one :class:`Question`
    for each required field that is absent or blank.

    Required fields checked:

    - ``cv:WorkHistory``: ``employedIn``, ``jobTitle``, ``startDate``,
      ``endDate``, ``jobDescription``
    - ``cvx:Project``: ``projectName``, ``projectDescription``, ``roleTitle``,
      ``startDate``, ``activitiesPerformed``, ``benefitsDelivered``,
      ``usesSkill`` (at least one link)

    Args:
        ttl_file: Path to a Turtle RDF file.

    Returns:
        Flat list of :class:`Question` objects, one per missing field per node,
        ordered WorkHistory-first then Projects.

    Raises:
        rdflib.exceptions.ParserError: If the file contains invalid Turtle.
    """
    g = Graph()
    g.parse(str(ttl_file), format="turtle")
    questions: list[Question] = []

    for wh in g.subjects(RDF.type, _CV.WorkHistory):
        slug = _slug_of(wh)

        company_iri_str = _get_one(g, wh, _CV.employedIn)
        company_name = None
        if company_iri_str:
            company_name = _get_one(g, URIRef(company_iri_str), _CV.Name)
        label = company_name or slug

        if not company_iri_str:
            questions.append(Question(
                slug=slug, field="employedIn",
                question=f"Which company or employer does the position '{slug}' belong to?",
            ))

        for pred, field, tmpl in [
            (_CV.jobTitle,       "jobTitle",       f"What was your job title at {label}?"),
            (_CV.startDate,      "startDate",      f"When did you start at {label} (YYYY-MM-DD)?"),
            (_CV.endDate,        "endDate",        f"When did you leave {label}, or is this your current role (YYYY-MM-DD or 'present')?"),
            (_CV.jobDescription, "jobDescription", f"Briefly describe your responsibilities at {label}."),
        ]:
            if not _get_one(g, wh, pred):
                questions.append(Question(slug=slug, field=field, question=tmpl))

        for proj in g.objects(wh, _CVX.hasProject):
            proj_slug = _slug_of(proj)
            proj_name = _get_one(g, proj, _CVX.projectName) or proj_slug

            for pred, field, tmpl in [
                (_CVX.projectName,         "projectName",         f"What is the name of project '{proj_slug}'?"),
                (_CVX.projectDescription,  "projectDescription",  f"What was project '{proj_name}' about?"),
                (_CVX.roleTitle,           "roleTitle",           f"What was your role on project '{proj_name}'?"),
                (_CVX.startDate,           "startDate",           f"When did project '{proj_name}' start (YYYY-MM-DD)?"),
                (_CVX.activitiesPerformed, "activitiesPerformed", f"What activities did you perform on project '{proj_name}'?"),
                (_CVX.benefitsDelivered,   "benefitsDelivered",   f"What outcomes or benefits did project '{proj_name}' deliver?"),
            ]:
                if not _get_one(g, proj, pred):
                    questions.append(Question(slug=proj_slug, field=field, question=tmpl))

            if not _has_any(g, proj, _CVX.usesSkill):
                questions.append(Question(
                    slug=proj_slug, field="usesSkill",
                    question=f"Which skills were used on project '{proj_name}'? (provide skill slugs or names)",
                ))

    return questions


# ─────────────────────────────────────────────────────────────────────────────
# Field update
# ─────────────────────────────────────────────────────────────────────────────

# Maps field name → (predicate URIRef, value_type)
# value_type: "literal" | "date" | "integer" | "uri"
_FIELD_MAP: dict[str, tuple[URIRef, str]] = {
    # cv:WorkHistory
    "jobTitle":              (_CV.jobTitle,              "literal"),
    "jobDescription":        (_CV.jobDescription,        "literal"),
    # cv:Company
    "Name":                  (_CV.Name,                  "literal"),
    "URL":                   (_CV.URL,                   "uri"),
    "Industry":              (_CV.Industry,              "literal"),
    "Locality":              (_CV.Locality,              "literal"),
    "Country":               (_CV.Country,               "literal"),
    # cvx:Project / cvx:PersonalProject
    "projectName":           (_CVX.projectName,          "literal"),
    "projectDescription":    (_CVX.projectDescription,   "literal"),
    "clientName":            (_CVX.clientName,           "literal"),
    "roleTitle":             (_CVX.roleTitle,            "literal"),
    "activitiesPerformed":   (_CVX.activitiesPerformed,  "literal"),
    "benefitsDelivered":     (_CVX.benefitsDelivered,    "literal"),
    "domain":                (_CVX.domain,               "literal"),
    "projectURL":            (_CVX.projectURL,           "uri"),
    "technologiesUsed":      (_CVX.technologiesUsed,     "literal"),
    # cv:Skill
    "skillName":             (_CV.skillName,             "literal"),
    "skillLevel":            (_CV.skillLevel,            "literal"),
    "skillYearsExperience":  (_CV.skillYearsExperience,  "integer"),
    # cv:Education
    "degreeType":            (_CV.degreeType,            "literal"),
    "eduMajor":              (_CV.eduMajor,              "literal"),
    "eduStartDate":          (_CV.eduStartDate,          "date"),
    "eduGradDate":           (_CV.eduGradDate,           "date"),
    # cvx:MOOC
    "courseTitle":           (_CVX.courseTitle,          "literal"),
    "courseProvider":        (_CVX.courseProvider,       "literal"),
    "issuingBody":           (_CVX.issuingBody,          "literal"),
    "completionDate":        (_CVX.completionDate,       "date"),
    "credentialURL":         (_CVX.credentialURL,        "uri"),
    "courseTopics":          (_CVX.courseTopics,         "literal"),
    # cvx:Training
    "trainingTitle":         (_CVX.trainingTitle,        "literal"),
    "trainingProvider":      (_CVX.trainingProvider,     "literal"),
    "trainingDate":          (_CVX.trainingDate,         "date"),
    "trainingDuration":      (_CVX.trainingDuration,     "literal"),
    "certificationName":     (_CVX.certificationName,    "literal"),
    "trainingTopics":        (_CVX.trainingTopics,       "literal"),
    # Publications (dcterms / bibo / cvx)
    "title":                 (_DCTERMS.title,            "literal"),
    "date":                  (_DCTERMS.date,             "date"),
    "doi":                   (_BIBO.doi,                 "literal"),
    "abstract":              (_CVX.abstract,             "literal"),
    "publicationVenue":      (_CVX.publicationVenue,     "literal"),
    "coAuthors":             (_CVX.coAuthors,            "literal"),
    # foaf:Person / cv:CV
    "name":                  (_FOAF.name,                "literal"),
    "mbox":                  (_FOAF.mbox,                "uri"),
    "homepage":              (_FOAF.homepage,            "uri"),
    "cvTitle":               (_CV.cvTitle,               "literal"),
    "lastUpdate":            (_CV.lastUpdate,            "date"),
}

# Fields that exist in both cv: and cvx: namespaces — prefer whichever already
# has a triple on the target node; fall back to cv:.
_AMBIGUOUS: dict[str, tuple[URIRef, URIRef]] = {
    "startDate": (_CV.startDate, _CVX.startDate),
    "endDate":   (_CV.endDate,   _CVX.endDate),
}


def _resolve_iri(g: Graph, slug_or_iri: str) -> URIRef:
    """Return the :class:`rdflib.URIRef` for a node identified by slug or IRI.

    Resolution order:

    1. If *slug_or_iri* starts with ``http://`` or ``https://``, use it directly.
    2. Try ``<http://example.org/cv/><slug_or_iri>``.
    3. Scan all subject IRIs for one whose local name matches *slug_or_iri*.

    Args:
        g:            The loaded RDF graph.
        slug_or_iri:  Slug (e.g. ``wh_acme_2019``) or full IRI string.

    Returns:
        The matching :class:`~rdflib.URIRef`.

    Raises:
        KeyError: If no matching node is found in the graph.
    """
    if slug_or_iri.startswith("http://") or slug_or_iri.startswith("https://"):
        return URIRef(slug_or_iri)

    candidate = URIRef(_BASE + slug_or_iri)
    if any(True for _ in g.triples((candidate, None, None))):
        return candidate

    for subj in g.subjects():
        if isinstance(subj, URIRef):
            s = str(subj)
            if s.endswith("/" + slug_or_iri) or s.endswith("#" + slug_or_iri):
                return subj

    raise KeyError(f"No node found for {slug_or_iri!r}. Check the slug or use a full IRI.")


def _make_rdf_value(raw: str, value_type: str):
    if value_type == "uri":
        return URIRef(raw)
    if value_type == "date":
        return Literal(raw, datatype=XSD.date)
    if value_type == "integer":
        return Literal(int(raw), datatype=XSD.integer)
    return Literal(raw)


def update_field(
    ttl_file: str | Path,
    slug_or_iri: str,
    field: str,
    value: str,
) -> None:
    """Update a single predicate on an RDF node and save the file in-place.

    Resolves the subject node from *slug_or_iri*, determines the RDF predicate
    from *field*, removes any existing triple for that predicate on the subject,
    adds the new value, and re-serialises the Turtle file.

    Supported field names and their predicates:

    +-----------------------+----------------------------+----------+
    | Field name            | Predicate                  | Type     |
    +=======================+============================+==========+
    | ``jobTitle``          | ``cv:jobTitle``            | string   |
    | ``startDate``         | ``cv:`` or ``cvx:``        | date     |
    | ``endDate``           | ``cv:`` or ``cvx:``        | date     |
    | ``jobDescription``    | ``cv:jobDescription``      | string   |
    | ``Name``              | ``cv:Name``                | string   |
    | ``projectName``       | ``cvx:projectName``        | string   |
    | ``projectDescription``| ``cvx:projectDescription`` | string   |
    | ``roleTitle``         | ``cvx:roleTitle``          | string   |
    | ``activitiesPerformed``| ``cvx:activitiesPerformed``| string  |
    | ``benefitsDelivered`` | ``cvx:benefitsDelivered``  | string   |
    | ``skillName``         | ``cv:skillName``           | string   |
    | ``skillYearsExperience``| ``cv:skillYearsExperience``| integer|
    | ``degreeType``        | ``cv:degreeType``          | string   |
    | ``courseTitle``       | ``cvx:courseTitle``        | string   |
    | ``trainingTitle``     | ``cvx:trainingTitle``      | string   |
    | ``title``             | ``dcterms:title``          | string   |
    | ``date``              | ``dcterms:date``           | date     |
    | ``name``              | ``foaf:name``              | string   |
    +-----------------------+----------------------------+----------+

    Args:
        ttl_file:    Path to the Turtle file to modify (updated in-place).
        slug_or_iri: Local slug (e.g. ``wh_acme_2019``) or full IRI of the node.
        field:       Field/predicate name (see table above).
        value:       New string value.  Dates must be ``YYYY-MM-DD``; URIs must
                     start with ``http://`` or ``https://``.

    Raises:
        KeyError:   If the node or field name cannot be resolved.
        ValueError: If the value cannot be coerced to the expected type.
    """
    path = Path(ttl_file)
    g = Graph()
    g.parse(str(path), format="turtle")

    subject = _resolve_iri(g, slug_or_iri)

    if field in _AMBIGUOUS:
        cv_pred, cvx_pred = _AMBIGUOUS[field]
        predicate = cvx_pred if _has_any(g, subject, cvx_pred) else cv_pred
        value_type = "date"
    elif field in _FIELD_MAP:
        predicate, value_type = _FIELD_MAP[field]
    else:
        raise KeyError(
            f"Unknown field {field!r}. "
            f"Supported fields: {', '.join(sorted(_FIELD_MAP) + list(_AMBIGUOUS))}"
        )

    rdf_value = _make_rdf_value(value, value_type)

    for triple in list(g.triples((subject, predicate, None))):
        g.remove(triple)
    g.add((subject, predicate, rdf_value))

    g.serialize(destination=str(path), format="turtle")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-points
# ─────────────────────────────────────────────────────────────────────────────

def audit_main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-audit``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="cv-audit",
        description="Audit a Turtle RDF CV for missing or empty fields.",
    )
    parser.add_argument("ttl_file", metavar="FILE.ttl",
                        help="Turtle RDF file to audit.")
    parser.add_argument("--json", action="store_true",
                        help="Output questions as JSON array.")

    args = parser.parse_args(argv)
    path = Path(args.ttl_file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    questions = audit_experience(path)

    if not questions:
        print("No missing fields found — CV looks complete!")
        return

    if args.json:
        import json
        print(json.dumps(
            [{"slug": q.slug, "field": q.field, "question": q.question}
             for q in questions],
            indent=2,
        ))
    else:
        print(f"Found {len(questions)} question(s):\n")
        for q in questions:
            print(f"  [{q.slug}]  {q.field}")
            print(f"    {q.question}")
            print()


def update_main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-update``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="cv-update",
        description="Update a single field on a node in a Turtle RDF CV file.",
        epilog=(
            "Examples:\n"
            "  cv-update cv.ttl wh_acme_2019 jobTitle 'Senior Engineer'\n"
            "  cv-update cv.ttl proj_smartgrid_2022 startDate 2021-03-01\n"
            "  cv-update cv.ttl wh_acme_2019 endDate 2023-06-30\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ttl_file",     metavar="FILE.ttl",
                        help="Turtle RDF file to update.")
    parser.add_argument("slug_or_iri",  metavar="SLUG_OR_IRI",
                        help="Node slug (e.g. wh_acme_2019) or full IRI.")
    parser.add_argument("field",        metavar="FIELD",
                        help="Field name (e.g. jobTitle, startDate, roleTitle).")
    parser.add_argument("value",        metavar="VALUE",
                        help="New value (dates as YYYY-MM-DD; URIs as https://...).")

    args = parser.parse_args(argv)
    path = Path(args.ttl_file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        update_field(path, args.slug_or_iri, args.field, args.value)
        print(f"Updated [{args.slug_or_iri}].{args.field} = {args.value!r}")
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    audit_main()
