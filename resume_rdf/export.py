"""
resume_rdf.export
=================
Convert a CV Turtle file to clean, human-readable Markdown.

``ttl_to_markdown(ttl_file) → str`` produces Markdown similar in style
to a hand-written consultant CV — person header, skills, professional
experience with nested projects, education, training/MOOCs, personal
projects, and publications.

Requires
--------
``rdflib >= 6.0``  (``pip install rdflib`` or ``pip install "resume-rdf[validate]"``)

CLI usage
---------
::

    cv-to-md my_cv.ttl                   # print to stdout
    cv-to-md my_cv.ttl --output cv.md    # write to file

Library usage
-------------
::

    from resume_rdf.export import ttl_to_markdown

    md = ttl_to_markdown("my_cv.ttl")
    print(md)

    with open("my_cv.md", "w") as f:
        f.write(ttl_to_markdown("my_cv.ttl"))
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from rdflib import Graph, Namespace, RDF
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "resume_rdf.export requires rdflib.\n"
        "pip install rdflib  or  pip install \"resume-rdf[validate]\""
    ) from _e

_CV      = Namespace("http://purl.org/captsolo/resume-rdf/0.2/cv#")
_CVX     = Namespace("http://example.org/cv-extension#")
_FOAF    = Namespace("http://xmlns.com/foaf/0.1/")
_DCTERMS = Namespace("http://purl.org/dc/terms/")
_BIBO    = Namespace("http://purl.org/ontology/bibo/")

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get(g: Graph, subj, pred, default: str = "") -> str:
    val = next(g.objects(subj, pred), None)
    return str(val).strip() if val else default


def _all(g: Graph, subj, pred) -> list[str]:
    return [str(o).strip() for o in g.objects(subj, pred) if str(o).strip()]


def _fmt_date(date_str: str) -> str:
    """Format an ISO date string as 'Month YYYY', falling back to 'YYYY' or as-is."""
    parts = date_str.strip()[:10].split("-")
    try:
        year  = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 0
        if month and 1 <= month <= 12:
            return f"{_MONTH_NAMES[month]} {year}"
        return str(year)
    except (ValueError, IndexError):
        return date_str


def _fmt_range(start: str, end: str, present_label: str = "present") -> str:
    s = _fmt_date(start) if start else ""
    e = _fmt_date(end)   if end   else present_label
    if s and e:
        return f"{s} – {e}"
    if s:
        return f"{s} – {present_label}"
    return e


def _section(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return []
    return [f"## {title}", ""] + lines + ["", "---", ""]


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_header(g: Graph, person_iri, cv_iri) -> list[str]:
    name     = _get(g, person_iri, _FOAF.name,      "Unknown")
    cv_title = _get(g, cv_iri,     _CV.cvTitle,     "") if cv_iri else ""
    location = _get(g, person_iri, _FOAF.based_near,"")
    mbox     = _get(g, person_iri, _FOAF.mbox,      "").replace("mailto:", "")
    homepage = _get(g, person_iri, _FOAF.homepage,  "")
    phone    = _get(g, person_iri, _FOAF.phone,     "")

    lines = [f"# {name}"]
    if cv_title:
        lines.append(f"**{cv_title}**")
    lines.append("")

    contact = [p for p in [location, mbox, phone, homepage] if p]
    if contact:
        lines.append(" | ".join(contact))
        lines.append("")

    lines += ["---", ""]
    return lines


def _build_skills(g: Graph, cv_iri) -> list[str]:
    if not cv_iri:
        return []
    skills = []
    for sk_iri in g.objects(cv_iri, _CV.hasSkill):
        name  = _get(g, sk_iri, _CV.skillName,             "")
        level = _get(g, sk_iri, _CV.skillLevel,            "")
        years = _get(g, sk_iri, _CV.skillYearsExperience,  "")
        if name:
            entry = name
            extras = [p for p in [level, (f"{years} yr" if years else "")] if p]
            if extras:
                entry += f" *({', '.join(extras)})*"
            skills.append(f"- {entry}")

    return _section("Core Skills", skills)


def _build_work(g: Graph, cv_iri, person_iri) -> list[str]:
    source = cv_iri or person_iri
    if not source:
        return []

    # Collect all work history entries
    entries = []
    for wh_iri in g.objects(source, _CV.hasWorkHistory):
        company_iri = next(g.objects(wh_iri, _CV.employedIn), None)
        job_title   = _get(g, wh_iri, _CV.jobTitle,       "")
        start       = _get(g, wh_iri, _CV.startDate,      "")
        end         = _get(g, wh_iri, _CV.endDate,        "")
        desc        = _get(g, wh_iri, _CV.jobDescription,  "")

        company_name = ""
        company_loc  = ""
        company_ind  = ""
        if company_iri:
            company_name = _get(g, company_iri, _CV.Name,     "")
            company_loc  = _get(g, company_iri, _CV.Locality, "")
            company_ind  = _get(g, company_iri, _CV.Industry, "")

        projects = []
        for proj_iri in g.objects(wh_iri, _CVX.hasProject):
            p_name   = _get(g, proj_iri, _CVX.projectName,         "")
            p_role   = _get(g, proj_iri, _CVX.roleTitle,           "")
            p_client = _get(g, proj_iri, _CVX.clientName,          "")
            p_start  = _get(g, proj_iri, _CVX.startDate,           "")
            p_end    = _get(g, proj_iri, _CVX.endDate,             "")
            p_desc   = _get(g, proj_iri, _CVX.projectDescription,  "")
            p_acts   = _get(g, proj_iri, _CVX.activitiesPerformed, "")
            p_bens   = _get(g, proj_iri, _CVX.benefitsDelivered,   "")
            domains  = _all(g, proj_iri, _CVX.domain)
            skill_names = [
                _get(g, sk, _CV.skillName, "")
                for sk in g.objects(proj_iri, _CVX.usesSkill)
                if _get(g, sk, _CV.skillName, "")
            ]
            projects.append({
                "name": p_name, "role": p_role, "client": p_client,
                "start": p_start, "end": p_end,
                "desc": p_desc, "acts": p_acts, "bens": p_bens,
                "domains": domains, "skills": skill_names,
                "sort_key": p_start,
            })

        projects.sort(key=lambda p: p["sort_key"], reverse=True)
        entries.append({
            "company": company_name, "loc": company_loc, "ind": company_ind,
            "title": job_title, "start": start, "end": end, "desc": desc,
            "projects": projects,
            "sort_key": start,
        })

    if not entries:
        return []

    entries.sort(key=lambda e: e["sort_key"], reverse=True)
    lines = ["## Professional Experience", ""]

    for e in entries:
        lines.append(f"### {e['company'] or 'Employer'}")
        meta = []
        if e["loc"]:
            meta.append(e["loc"])
        if e["ind"]:
            meta.append(e["ind"])
        date_range = _fmt_range(e["start"], e["end"])
        if date_range:
            meta.append(date_range)
        if meta:
            lines.append(f"*{' | '.join(meta)}*")
        lines.append("")
        if e["title"]:
            lines.append(f"**{e['title']}**")
            lines.append("")
        if e["desc"]:
            lines.append(e["desc"])
            lines.append("")

        for p in e["projects"]:
            lines.append(f"#### {p['name']}")
            pmeta = []
            if p["client"] and p["client"] != e["company"]:
                pmeta.append(p["client"])
            if p["role"]:
                pmeta.append(p["role"])
            prange = _fmt_range(p["start"], p["end"])
            if prange:
                pmeta.append(prange)
            if pmeta:
                lines.append(f"*{' | '.join(pmeta)}*")
            lines.append("")
            if p["desc"]:
                lines.append(p["desc"])
                lines.append("")
            if p["acts"]:
                lines.append("**Activities:**")
                lines.append(p["acts"])
                lines.append("")
            if p["bens"]:
                lines.append("**Outcomes:** " + p["bens"])
                lines.append("")
            if p["skills"]:
                lines.append(f"*Skills: {', '.join(p['skills'])}*")
                lines.append("")
            if p["domains"]:
                lines.append(f"*Sectors: {', '.join(p['domains'])}*")
                lines.append("")

        lines.append("---")
        lines.append("")

    return lines


def _build_education(g: Graph, cv_iri) -> list[str]:
    if not cv_iri:
        return []
    items = []
    for edu_iri in g.objects(cv_iri, _CV.hasEducation):
        degree   = _get(g, edu_iri, _CV.degreeType,   "")
        major    = _get(g, edu_iri, _CV.eduMajor,     "")
        start    = _get(g, edu_iri, _CV.eduStartDate, "")
        grad     = _get(g, edu_iri, _CV.eduGradDate,  "")
        school_iri = next(g.objects(edu_iri, _CV.studiedIn), None)
        school   = _get(g, school_iri, _CV.Name, "") if school_iri else ""
        loc      = _get(g, school_iri, _CV.Locality, "") if school_iri else ""

        heading = " – ".join(p for p in [degree, major] if p) or "Degree"
        lines = [f"**{heading}**"]
        meta = [p for p in [school, loc, _fmt_range(start, grad)] if p]
        if meta:
            lines.append(f"*{' | '.join(meta)}*")
        items.extend(lines)
        items.append("")

    return _section("Education", items)


def _build_training(g: Graph, cv_iri) -> list[str]:
    if not cv_iri:
        return []
    items = []
    for tr_iri in g.objects(cv_iri, _CVX.hasTraining):
        title    = _get(g, tr_iri, _CVX.trainingTitle,    "")
        provider = _get(g, tr_iri, _CVX.trainingProvider, "")
        date_str = _get(g, tr_iri, _CVX.trainingDate,     "")
        cert     = _get(g, tr_iri, _CVX.certificationName,"")
        parts = [f"**{title or 'Training'}**"]
        if provider:
            parts.append(provider)
        if date_str:
            parts.append(_fmt_date(date_str))
        entry = " — ".join(parts)
        if cert and cert != title:
            entry += f" *(cert: {cert})*"
        items.append(f"- {entry}")

    for mooc_iri in g.objects(cv_iri, _CVX.hasMOOC):
        title    = _get(g, mooc_iri, _CVX.courseTitle,    "")
        provider = _get(g, mooc_iri, _CVX.courseProvider, "")
        date_str = _get(g, mooc_iri, _CVX.completionDate, "")
        parts    = [f"**{title or 'MOOC'}**"]
        if provider:
            parts.append(provider)
        if date_str:
            parts.append(_fmt_date(date_str))
        items.append(f"- {' — '.join(parts)}")

    return _section("Certifications & Training", items)


def _build_personal_projects(g: Graph, cv_iri) -> list[str]:
    if not cv_iri:
        return []
    items = []
    for pp_iri in g.objects(cv_iri, _CVX.hasPersonalProject):
        name = _get(g, pp_iri, _CVX.projectName,        "Personal Project")
        desc = _get(g, pp_iri, _CVX.projectDescription, "")
        url  = _get(g, pp_iri, _CVX.projectURL,         "")
        tech = _get(g, pp_iri, _CVX.technologiesUsed,   "")
        start = _get(g, pp_iri, _CVX.startDate, "")
        end   = _get(g, pp_iri, _CVX.endDate,   "")
        date_range = _fmt_range(start, end)

        items.append(f"### {name}")
        if date_range:
            items.append(f"*{date_range}*")
            items.append("")
        if desc:
            items.append(desc)
            items.append("")
        if tech:
            items.append(f"*Technologies: {tech}*")
        if url:
            items.append(f"*URL: {url}*")
        items.append("")

    return _section("Personal Projects", items)


def _build_publications(g: Graph, cv_iri) -> list[str]:
    if not cv_iri:
        return []
    items = []
    for pub_iri in g.objects(cv_iri, _CVX.hasPublication):
        title   = _get(g, pub_iri, _DCTERMS.title,       "")
        date_s  = _get(g, pub_iri, _DCTERMS.date,        "")
        venue   = _get(g, pub_iri, _CVX.publicationVenue,"")
        doi     = _get(g, pub_iri, _BIBO.doi,            "")
        uri     = _get(g, pub_iri, _BIBO.uri,            "")
        authors = _get(g, pub_iri, _CVX.coAuthors,       "")
        abstract= _get(g, pub_iri, _CVX.abstract,        "")

        lines = [f"**{title or 'Publication'}**"]
        meta  = [p for p in [venue, (_fmt_date(date_s) if date_s else "")] if p]
        if meta:
            lines.append(f"*{', '.join(meta)}*")
        if authors:
            lines.append(f"Co-authors: {authors}")
        if doi:
            lines.append(f"DOI: {doi}")
        elif uri:
            lines.append(f"URL: {uri}")
        if abstract:
            lines.append(f"> {abstract}")

        items.extend(lines)
        items.append("")

    return _section("Publications", items)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def ttl_to_markdown(ttl_file: str | Path) -> str:
    """Convert a CV Turtle file to clean, human-readable Markdown.

    Extracts all structured content from the graph — person identity,
    skills, work history, projects, education, training, personal
    projects, and publications — and renders it as a Markdown document
    styled like a hand-written consultant CV.

    Args:
        ttl_file: Path to a Turtle RDF CV file.

    Returns:
        A Markdown string.  Sections with no content are omitted.

    Raises:
        rdflib.exceptions.ParserError: If the file contains invalid Turtle.

    Example::

        from resume_rdf.export import ttl_to_markdown

        md = ttl_to_markdown("my_cv.ttl")
        print(md)

        Path("my_cv.md").write_text(ttl_to_markdown("my_cv.ttl"))
    """
    g = Graph()
    g.parse(str(ttl_file), format="turtle")

    # Locate person and CV root
    cv_iri      = next(g.subjects(RDF.type, _CV.CV), None)
    person_iri  = (
        next(g.objects(cv_iri, _CV.aboutPerson), None) if cv_iri
        else next(g.subjects(RDF.type, _FOAF.Person), None)
    )

    sections: list[str] = []
    if person_iri:
        sections += _build_header(g, person_iri, cv_iri)
    sections += _build_skills(g, cv_iri)
    sections += _build_work(g, cv_iri, person_iri)
    sections += _build_education(g, cv_iri)
    sections += _build_training(g, cv_iri)
    sections += _build_personal_projects(g, cv_iri)
    sections += _build_publications(g, cv_iri)

    return "\n".join(sections).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-to-md``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="cv-to-md",
        description="Convert a Turtle RDF CV to human-readable Markdown.",
        epilog=(
            "Examples:\n"
            "  cv-to-md my_cv.ttl                  # print to stdout\n"
            "  cv-to-md my_cv.ttl --output cv.md   # write to file\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ttl_file", metavar="FILE.ttl",
                        help="Turtle RDF CV file to convert.")
    parser.add_argument("--output", "-o", metavar="FILE.md",
                        help="Write Markdown to this file (default: stdout).")

    args = parser.parse_args(argv)
    path = Path(args.ttl_file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    md = ttl_to_markdown(path)

    if args.output:
        out = Path(args.output)
        out.write_text(md, encoding="utf-8")
        print(f"Saved: {out}")
    else:
        print(md, end="")


if __name__ == "__main__":
    main()
