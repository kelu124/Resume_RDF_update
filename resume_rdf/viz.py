"""
resume_rdf.viz
==============
Render a CV Turtle file as a visual knowledge graph.

``visualize_cv(ttl_file, output_path)`` produces:

- An **interactive HTML** file (powered by pyvis) when *output_path* ends
  with ``.html`` — this is the default and gives the best result.
- A **static PNG / SVG / PDF** (networkx + matplotlib) when *output_path*
  ends with ``.png``, ``.svg``, or ``.pdf``.

Graph layout
------------
The person sits at the centre.  The hierarchy flows outward:

    Person → Employer → Project → Skill (used)
    Person → Education
    Person → Training / MOOC
    Person → Personal Project
    Person → Publication

Requires
--------
- HTML output: ``pip install pyvis rdflib``
- PNG/SVG output: ``pip install networkx matplotlib rdflib``
- Or: ``pip install "resume-rdf[viz]"``

CLI usage
---------
::

    cv-graph my_cv.ttl                      # → my_cv.html  (default)
    cv-graph my_cv.ttl --output cv.png      # → static PNG
    cv-graph my_cv.ttl --output cv.html     # → interactive HTML

Library usage
-------------
::

    from resume_rdf.viz import visualize_cv

    out = visualize_cv("my_cv.ttl")                   # → my_cv.html
    out = visualize_cv("my_cv.ttl", "graph.png")      # → graph.png
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from rdflib import Graph, Namespace, URIRef, RDF
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "resume_rdf.viz requires rdflib.\n"
        "pip install rdflib  or  pip install \"resume-rdf[viz]\""
    ) from _e

_CV      = Namespace("http://purl.org/captsolo/resume-rdf/0.2/cv#")
_CVX     = Namespace("http://example.org/cv-extension#")
_FOAF    = Namespace("http://xmlns.com/foaf/0.1/")
_DCTERMS = Namespace("http://purl.org/dc/terms/")
_BIBO    = Namespace("http://purl.org/ontology/bibo/")

# Visual style per node type (pyvis shape names; size is pyvis node size)
_NODE_STYLES: dict[str, dict] = {
    "person":          {"color": "#4e79a7", "shape": "star",    "size": 35, "mpl_size": 600},
    "company":         {"color": "#f28e2b", "shape": "square",  "size": 22, "mpl_size": 400},
    "project":         {"color": "#59a14f", "shape": "diamond", "size": 18, "mpl_size": 300},
    "skill":           {"color": "#9c755f", "shape": "dot",     "size": 11, "mpl_size": 150},
    "education":       {"color": "#edc948", "shape": "square",  "size": 16, "mpl_size": 250},
    "training":        {"color": "#bab0ac", "shape": "dot",     "size": 12, "mpl_size": 150},
    "mooc":            {"color": "#76b7b2", "shape": "dot",     "size": 12, "mpl_size": 150},
    "personal_project":{"color": "#e15759", "shape": "diamond", "size": 15, "mpl_size": 200},
    "publication":     {"color": "#b07aa1", "shape": "dot",     "size": 12, "mpl_size": 150},
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lbl(text: str, max_len: int = 28) -> str:
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _get(g: Graph, subj, pred, default: str = "") -> str:
    val = next(g.objects(subj, pred), None)
    return str(val).strip() if val else default


def _slug(iri) -> str:
    s = str(iri)
    for sep in ("#", "/"):
        idx = s.rfind(sep)
        if idx >= 0:
            return s[idx + 1:]
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Graph data extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_graph_data(
    ttl_file: Path,
) -> tuple[dict[str, dict], list[dict]]:
    """Parse *ttl_file* and return (nodes, edges) for rendering.

    Returns
    -------
    nodes : dict[iri_str → {label, type, tooltip}]
    edges : list[{from, to, label}]
    """
    g = Graph()
    g.parse(str(ttl_file), format="turtle")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    _seen_edges: set[tuple] = set()

    def add_node(iri, label: str, ntype: str, tooltip: str = ""):
        key = str(iri)
        if key not in nodes:
            nodes[key] = {
                "label":   _lbl(label),
                "type":    ntype,
                "tooltip": (tooltip or label).strip(),
            }

    def add_edge(src, dst, label: str = ""):
        key = (str(src), str(dst), label)
        if key not in _seen_edges:
            _seen_edges.add(key)
            edges.append({"from": str(src), "to": str(dst), "label": label})

    # ── Person ──────────────────────────────────────────────────────────────
    person_iri: URIRef | None = None
    cv_iri: URIRef | None = None

    for cv in g.subjects(RDF.type, _CV.CV):
        cv_iri = cv
        p = next(g.objects(cv, _CV.aboutPerson), None)
        if p:
            person_iri = p
            break

    if person_iri is None:
        person_iri = next(g.subjects(RDF.type, _FOAF.Person), None)

    if person_iri is None:
        return nodes, edges

    name = _get(g, person_iri, _FOAF.name, _slug(person_iri))
    email = _get(g, person_iri, _FOAF.mbox, "").replace("mailto:", "")
    homepage = _get(g, person_iri, _FOAF.homepage, "")
    location = _get(g, person_iri, _FOAF.based_near, "")
    cv_title = _get(g, cv_iri, _CV.cvTitle, "") if cv_iri else ""

    tooltip_parts = [name]
    if cv_title:
        tooltip_parts.append(cv_title)
    if location:
        tooltip_parts.append(location)
    if email:
        tooltip_parts.append(email)
    if homepage:
        tooltip_parts.append(homepage)
    add_node(person_iri, name, "person", "\n".join(tooltip_parts))

    # ── Work history → Companies → Projects → Skills ─────────────────────
    wh_source = cv_iri if cv_iri else person_iri
    for wh_iri in g.objects(wh_source, _CV.hasWorkHistory):
        company_iri = next(g.objects(wh_iri, _CV.employedIn), None)
        job_title   = _get(g, wh_iri, _CV.jobTitle, "worked at")
        start       = _get(g, wh_iri, _CV.startDate, "")[:4]
        end         = _get(g, wh_iri, _CV.endDate, "")[:4]

        if company_iri:
            company_name = _get(g, company_iri, _CV.Name, _slug(company_iri))
            locality     = _get(g, company_iri, _CV.Locality, "")
            industry     = _get(g, company_iri, _CV.Industry, "")
            date_range   = f"{start}–{end}" if end else (f"{start}–" if start else "")

            tip_parts = [company_name]
            if industry:
                tip_parts.append(industry)
            if locality:
                tip_parts.append(locality)
            if date_range:
                tip_parts.append(date_range)
            add_node(company_iri, company_name, "company", "\n".join(tip_parts))
            add_edge(person_iri, company_iri, job_title)
        else:
            company_iri = None

        for proj_iri in g.objects(wh_iri, _CVX.hasProject):
            proj_name  = _get(g, proj_iri, _CVX.projectName, _slug(proj_iri))
            role       = _get(g, proj_iri, _CVX.roleTitle, "")
            client     = _get(g, proj_iri, _CVX.clientName, "")
            p_start    = _get(g, proj_iri, _CVX.startDate, "")[:4]
            p_end      = _get(g, proj_iri, _CVX.endDate, "")[:4]
            p_desc     = _get(g, proj_iri, _CVX.projectDescription, "")
            date_range = f"{p_start}–{p_end}" if p_end else (f"{p_start}–" if p_start else "")

            tip_parts = [proj_name]
            if role:
                tip_parts.append(f"Role: {role}")
            if client:
                tip_parts.append(f"Client: {client}")
            if date_range:
                tip_parts.append(date_range)
            if p_desc:
                tip_parts.append(p_desc[:120] + ("…" if len(p_desc) > 120 else ""))

            add_node(proj_iri, proj_name, "project", "\n".join(tip_parts))
            if company_iri:
                add_edge(company_iri, proj_iri, role or "project")
            else:
                add_edge(person_iri, proj_iri, role or "project")

            for skill_iri in g.objects(proj_iri, _CVX.usesSkill):
                skill_name = _get(g, skill_iri, _CV.skillName, _slug(skill_iri))
                skill_level = _get(g, skill_iri, _CV.skillLevel, "")
                skill_years = _get(g, skill_iri, _CV.skillYearsExperience, "")
                tip = skill_name
                if skill_level:
                    tip += f"\n{skill_level}"
                if skill_years:
                    tip += f", {skill_years} yr"
                add_node(skill_iri, skill_name, "skill", tip)
                add_edge(proj_iri, skill_iri, "uses")

    # ── Education ───────────────────────────────────────────────────────────
    if cv_iri:
        for edu_iri in g.objects(cv_iri, _CV.hasEducation):
            degree  = _get(g, edu_iri, _CV.degreeType, "")
            major   = _get(g, edu_iri, _CV.eduMajor, "")
            school_iri = next(g.objects(edu_iri, _CV.studiedIn), None)
            school  = _get(g, school_iri, _CV.Name, "") if school_iri else ""
            start   = _get(g, edu_iri, _CV.eduStartDate, "")[:4]
            end     = _get(g, edu_iri, _CV.eduGradDate, "")[:4]

            label = degree or "Education"
            if major:
                label = f"{degree} – {major}" if degree else major
            tip_parts = [label]
            if school:
                tip_parts.append(school)
            if start or end:
                tip_parts.append(f"{start}–{end}")

            add_node(edu_iri, label, "education", "\n".join(tip_parts))
            add_edge(person_iri, edu_iri, "studied")

    # ── MOOCs ───────────────────────────────────────────────────────────────
    if cv_iri:
        for mooc_iri in g.objects(cv_iri, _CVX.hasMOOC):
            title    = _get(g, mooc_iri, _CVX.courseTitle, "MOOC")
            provider = _get(g, mooc_iri, _CVX.courseProvider, "")
            tip = title + (f"\n{provider}" if provider else "")
            add_node(mooc_iri, title, "mooc", tip)
            add_edge(person_iri, mooc_iri, "completed")

    # ── Training ────────────────────────────────────────────────────────────
    if cv_iri:
        for tr_iri in g.objects(cv_iri, _CVX.hasTraining):
            title    = _get(g, tr_iri, _CVX.trainingTitle, "Training")
            provider = _get(g, tr_iri, _CVX.trainingProvider, "")
            tip = title + (f"\n{provider}" if provider else "")
            add_node(tr_iri, title, "training", tip)
            add_edge(person_iri, tr_iri, "certified")

    # ── Personal Projects ───────────────────────────────────────────────────
    if cv_iri:
        for pp_iri in g.objects(cv_iri, _CVX.hasPersonalProject):
            pp_name = _get(g, pp_iri, _CVX.projectName, "Personal Project")
            pp_desc = _get(g, pp_iri, _CVX.projectDescription, "")
            tip = pp_name + (f"\n{pp_desc[:120]}" if pp_desc else "")
            add_node(pp_iri, pp_name, "personal_project", tip)
            add_edge(person_iri, pp_iri, "personal project")

    # ── Publications ────────────────────────────────────────────────────────
    if cv_iri:
        for pub_iri in g.objects(cv_iri, _CVX.hasPublication):
            title = _get(g, pub_iri, _DCTERMS.title, "Publication")
            venue = _get(g, pub_iri, _CVX.publicationVenue, "")
            tip = title + (f"\n{venue}" if venue else "")
            add_node(pub_iri, title, "publication", tip)
            add_edge(person_iri, pub_iri, "published")

    # Remove edges whose endpoints are not in nodes (defensive)
    edges[:] = [e for e in edges if e["from"] in nodes and e["to"] in nodes]

    return nodes, edges


# ─────────────────────────────────────────────────────────────────────────────
# HTML renderer (pyvis)
# ─────────────────────────────────────────────────────────────────────────────

def _render_html(
    nodes: dict,
    edges: list,
    output_path: Path,
    title: str = "CV Knowledge Graph",
) -> None:
    try:
        from pyvis.network import Network
    except ImportError as _e:  # pragma: no cover
        raise ImportError(
            "pyvis is required for HTML output.\n"
            "pip install pyvis  or  pip install \"resume-rdf[viz]\""
        ) from _e

    net = Network(
        height="820px",
        width="100%",
        bgcolor="#f5f5f5",
        font_color="#2d2d2d",
        directed=True,
        notebook=False,
        heading=title,
    )
    net.barnes_hut(
        gravity=-7000,
        central_gravity=0.12,
        spring_length=160,
        spring_strength=0.05,
        damping=0.09,
    )

    for node_id, attrs in nodes.items():
        style = _NODE_STYLES.get(attrs["type"], {"color": "#ccc", "shape": "dot", "size": 14})
        net.add_node(
            node_id,
            label=attrs["label"],
            title=attrs["tooltip"].replace("\n", "<br>"),
            color=style["color"],
            shape=style["shape"],
            size=style["size"],
        )

    for edge in edges:
        net.add_edge(
            edge["from"],
            edge["to"],
            label=edge["label"],
            title=edge["label"],
            font={"size": 8, "align": "middle"},
            arrows={"to": {"enabled": True, "scaleFactor": 0.6}},
            smooth={"type": "dynamic"},
        )

    # Inject a colour legend before saving
    legend_html = "".join(
        f'<span style="display:inline-block;margin:4px 8px;">'
        f'<span style="background:{st["color"]};display:inline-block;'
        f'width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:4px;"></span>'
        f'{ntype.replace("_", " ").title()}</span>'
        for ntype, st in _NODE_STYLES.items()
        if any(a["type"] == ntype for a in nodes.values())
    )
    net.html = net.html.replace(
        "</body>",
        f'<div style="position:fixed;bottom:10px;left:10px;background:rgba(255,255,255,0.9);'
        f'padding:8px 12px;border-radius:6px;font-family:sans-serif;font-size:12px;">'
        f'{legend_html}</div></body>',
    )

    net.save_graph(str(output_path))


# ─────────────────────────────────────────────────────────────────────────────
# Static renderer (networkx + matplotlib)
# ─────────────────────────────────────────────────────────────────────────────

def _render_static(
    nodes: dict,
    edges: list,
    output_path: Path,
    dpi: int = 150,
) -> None:
    try:
        import networkx as nx
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError as _e:  # pragma: no cover
        raise ImportError(
            "networkx and matplotlib are required for PNG/SVG/PDF output.\n"
            "pip install networkx matplotlib  or  pip install \"resume-rdf[viz]\""
        ) from _e

    G = nx.DiGraph()
    for nid, attrs in nodes.items():
        G.add_node(nid, **attrs)
    for edge in edges:
        G.add_edge(edge["from"], edge["to"], label=edge["label"])

    # Shell layout: person centre → companies → projects → everything else
    person_ids  = [n for n, a in nodes.items() if a["type"] == "person"]
    company_ids = [n for n, a in nodes.items() if a["type"] == "company"]
    project_ids = [n for n, a in nodes.items() if a["type"] == "project"]
    other_ids   = [
        n for n, a in nodes.items()
        if a["type"] not in ("person", "company", "project")
    ]

    shells = [s for s in [person_ids, company_ids, project_ids, other_ids] if s]
    if len(shells) < 2:
        pos = nx.spring_layout(G, k=2.5, seed=42)
    else:
        pos = nx.shell_layout(G, nlist=shells)

    node_order  = list(G.nodes())
    colors      = [_NODE_STYLES.get(nodes[n]["type"], {}).get("color", "#ccc") for n in node_order]
    sizes       = [_NODE_STYLES.get(nodes[n]["type"], {}).get("mpl_size", 150) for n in node_order]

    fig, ax = plt.subplots(figsize=(20, 14))
    ax.set_facecolor("#f8f8f8")
    fig.patch.set_facecolor("#f8f8f8")

    nx.draw_networkx_nodes(G, pos, nodelist=node_order,
                           node_color=colors, node_size=sizes, ax=ax, alpha=0.92)
    nx.draw_networkx_labels(
        G, pos,
        labels={n: attrs["label"] for n, attrs in nodes.items()},
        font_size=6.5, ax=ax,
    )
    nx.draw_networkx_edges(
        G, pos, edge_color="#aaaaaa", arrows=True,
        arrowsize=12, ax=ax, connectionstyle="arc3,rad=0.08",
        min_source_margin=8, min_target_margin=8,
    )
    edge_labels = {(e["from"], e["to"]): e["label"] for e in edges if e["label"]}
    nx.draw_networkx_edge_labels(
        G, pos, edge_labels=edge_labels,
        font_size=5.5, ax=ax, label_pos=0.4,
    )

    # Legend — only types that appear in this graph
    patches = [
        mpatches.Patch(color=st["color"], label=ntype.replace("_", " ").title())
        for ntype, st in _NODE_STYLES.items()
        if any(a["type"] == ntype for a in nodes.values())
    ]
    ax.legend(handles=patches, loc="upper right", fontsize=8, framealpha=0.85)
    ax.axis("off")

    plt.tight_layout(pad=0.3)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def visualize_cv(
    ttl_file: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Render a CV Turtle file as a visual knowledge graph.

    Produces an interactive HTML file (pyvis) or a static image
    (networkx + matplotlib), chosen by *output_path*'s suffix.

    Node colours
    ~~~~~~~~~~~~
    - Blue star    — Person
    - Orange       — Employer (cv:Company)
    - Green        — Project (cvx:Project)
    - Brown        — Skill (cv:Skill, from project cvx:usesSkill links)
    - Yellow       — Education (cv:Education)
    - Grey         — Training / Certification (cvx:Training)
    - Teal         — Online course (cvx:MOOC)
    - Red          — Personal project (cvx:PersonalProject)
    - Purple       — Publication (bibo:*)

    Args:
        ttl_file:    Path to the Turtle RDF file.
        output_path: Destination path.  Extension determines format:
                     ``.html`` → interactive HTML (default);
                     ``.png`` / ``.svg`` / ``.pdf`` → static image.
                     Defaults to *ttl_file* with ``.html`` extension.

    Returns:
        Path to the saved output file.

    Raises:
        ImportError: If the required rendering library is not installed.
        rdflib.exceptions.ParserError: If the TTL file is malformed.

    Example::

        from resume_rdf.viz import visualize_cv

        visualize_cv("frodo.ttl")                   # → frodo.html
        visualize_cv("frodo.ttl", "frodo.png")      # → frodo.png
    """
    path = Path(ttl_file)
    if output_path is None:
        output_path = path.with_suffix(".html")
    output_path = Path(output_path)

    nodes, edges = _extract_graph_data(path)

    suffix = output_path.suffix.lower()
    if suffix in (".png", ".svg", ".pdf"):
        _render_static(nodes, edges, output_path)
    else:
        _render_html(nodes, edges, output_path, title=f"CV — {path.stem}")

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-graph``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="cv-graph",
        description="Render a Turtle RDF CV as a visual knowledge graph.",
        epilog=(
            "Examples:\n"
            "  cv-graph frodo.ttl                  # interactive HTML\n"
            "  cv-graph frodo.ttl --output cv.png  # static PNG\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ttl_file", metavar="FILE.ttl",
                        help="Turtle RDF file to visualise.")
    parser.add_argument("--output", "-o", metavar="OUTPUT",
                        help="Output path (.html default; .png/.svg/.pdf for static).")

    args = parser.parse_args(argv)
    path = Path(args.ttl_file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    out = visualize_cv(path, args.output)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
