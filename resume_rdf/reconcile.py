"""
resume_rdf.reconcile
====================
Cross-TTL entity reconciliation: find projects and employer/client nodes that
describe the same real-world thing across multiple Turtle files, then rewrite
them to share a single canonical IRI so the graphs can be joined via SPARQL.

Algorithm
---------
1. Parse every TTL file with rdflib.
2. Extract *Project* nodes (labelled by ``cvx:projectName``) and *Company*
   nodes (labelled by ``cv:Name``) from each file.
3. For every cross-file pair of the same entity type, compute a string
   similarity score with :mod:`difflib`.
4. Surface pairs whose score meets *threshold* to the user one by one.
5. On confirmation, record ``old_iri → canonical_iri`` in a mapping (the IRI
   from the file listed **first** on the command line is kept as canonical).
6. Rewrite all TTL files: replace every occurrence of a retired IRI with its
   canonical counterpart, then re-serialise with rdflib.

Requires
--------
``rdflib >= 6.0``  (``pip install rdflib`` or ``pip install "resume-rdf[validate]"``)

CLI usage
---------
::

    cv-reconcile file1.ttl file2.ttl file3.ttl
    cv-reconcile *.ttl --threshold 0.80
    cv-reconcile file1.ttl file2.ttl --dry-run
    cv-reconcile file1.ttl file2.ttl --yes   # accept all matches

Library usage
-------------
::

    from resume_rdf.reconcile import reconcile_interactive
    from pathlib import Path

    n = reconcile_interactive(
        [Path("alice.ttl"), Path("bob.ttl")],
        threshold=0.75,
    )
    print(f"{n} merge(s) applied")
"""

import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

try:
    from rdflib import Graph, Namespace, URIRef
    from rdflib.term import Literal
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "resume_rdf.reconcile requires rdflib.\n"
        "Install it with:  pip install rdflib\n"
        "or:               pip install \"resume-rdf[validate]\""
    ) from _e

_CV  = Namespace("http://purl.org/captsolo/resume-rdf/0.2/cv#")
_CVX = Namespace("http://example.org/cv-extension#")

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Entity:
    """An RDF entity extracted from a Turtle file.

    Attributes:
        iri:    The subject IRI of the entity in its source graph.
        label:  Human-readable label used for similarity comparison.
        kind:   ``"project"`` or ``"company"``.
        source: Path to the TTL file this entity came from.
    """
    iri:    URIRef
    label:  str
    kind:   str
    source: Path


@dataclass(frozen=True)
class Match:
    """A candidate duplicate pair surfaced by :func:`find_matches`.

    Attributes:
        a:     Entity from the earlier file (kept as canonical on merge).
        b:     Entity from the later file (IRI replaced on merge).
        score: Normalised similarity in ``[0, 1]``.
    """
    a:     Entity
    b:     Entity
    score: float


# ─────────────────────────────────────────────────────────────────────────────
# Core logic
# ─────────────────────────────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    """Return a normalised similarity score in ``[0, 1]`` for two strings.

    Uses :class:`difflib.SequenceMatcher` after case-folding, which handles
    small edits, reorderings, and common abbreviations reasonably well without
    any third-party dependencies.

    Args:
        a: First string.
        b: Second string.

    Returns:
        A float in ``[0.0, 1.0]`` where 1.0 means identical.
    """
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def load_entities(ttl_files: list[Path]) -> list[Entity]:
    """Parse TTL files and extract labelled Project and Company entities.

    Extracted node types:

    - ``cvx:Project`` — labelled by ``cvx:projectName``
    - ``cv:Company``  — labelled by ``cv:Name``

    Args:
        ttl_files: Ordered list of Turtle file paths.  The order matters:
            when two entities are merged the one from the earlier file is
            kept as canonical.

    Returns:
        Flat list of :class:`Entity` objects, one per labelled node per file.

    Raises:
        rdflib.exceptions.ParserError: If a file contains invalid Turtle.
    """
    entities: list[Entity] = []
    for path in ttl_files:
        g = Graph()
        g.parse(str(path), format="turtle")

        for iri, _, name in g.triples((None, _CVX.projectName, None)):
            if isinstance(iri, URIRef):
                entities.append(Entity(iri=iri, label=str(name), kind="project", source=path))

        for iri, _, name in g.triples((None, _CV.Name, None)):
            if isinstance(iri, URIRef):
                entities.append(Entity(iri=iri, label=str(name), kind="company", source=path))

    return entities


def find_matches(entities: list[Entity], threshold: float = 0.75) -> list[Match]:
    """Find cross-file entity pairs whose labels are similar enough to be candidates.

    Pairs where both entities come from the same file, or share an identical
    IRI, are skipped.  Only pairs of the same ``kind`` are compared.

    Args:
        entities: List of entities returned by :func:`load_entities`.
        threshold: Minimum similarity score to include a pair.
            ``0.75`` is a good default; lower it to catch more candidates,
            raise it to reduce false positives.

    Returns:
        List of :class:`Match` objects sorted by score descending.
    """
    by_kind: dict[str, list[Entity]] = {}
    for e in entities:
        by_kind.setdefault(e.kind, []).append(e)

    matches: list[Match] = []
    for kind_group in by_kind.values():
        for i, a in enumerate(kind_group):
            for b in kind_group[i + 1:]:
                if a.source == b.source:
                    continue
                if a.iri == b.iri:
                    continue
                score = _similarity(a.label, b.label)
                if score >= threshold:
                    # keep the entity from the earlier file as `a`
                    if a.source > b.source:
                        a, b = b, a
                    matches.append(Match(a=a, b=b, score=score))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def apply_mapping(ttl_files: list[Path], mapping: dict[URIRef, URIRef]) -> dict[Path, int]:
    """Rewrite TTL files using the confirmed ``old_iri → canonical_iri`` mapping.

    For each file, triples whose subject or object IRI appears in *mapping*
    are replaced in-place.  The file is only re-serialised if at least one
    replacement was made.

    Args:
        ttl_files: Paths to rewrite (all files passed to the reconciler).
        mapping:   Dict mapping retired IRIs to their canonical replacements.

    Returns:
        Dict ``{path: n_triples_rewritten}`` for every file that changed.
    """
    results: dict[Path, int] = {}
    for path in ttl_files:
        g = Graph()
        g.parse(str(path), format="turtle")

        n_replaced = 0
        for old_iri, canonical_iri in mapping.items():
            affected = [
                (s, p, o) for s, p, o in g
                if s == old_iri or (isinstance(o, URIRef) and o == old_iri)
            ]
            if not affected:
                continue
            n_replaced += len(affected)
            for s, p, o in affected:
                g.remove((s, p, o))
                new_s = canonical_iri if s == old_iri else s
                new_o = canonical_iri if isinstance(o, URIRef) and o == old_iri else o
                g.add((new_s, p, new_o))

        if n_replaced > 0:
            g.serialize(destination=str(path), format="turtle")
            results[path] = n_replaced

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Within-graph deduplication
# ─────────────────────────────────────────────────────────────────────────────

# Predicate / type URIs used for within-graph deduplication
_CV_STR  = "http://purl.org/captsolo/resume-rdf/0.2/cv#"
_CVX_STR = "http://example.org/cv-extension#"
_BIBO    = "http://purl.org/ontology/bibo/"
_DCT     = "http://purl.org/dc/terms/"

_RDF_TYPE       = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

# Skills
_SKILL_NAME     = URIRef(f"{_CV_STR}skillName")
_SKILL_LVL      = URIRef(f"{_CV_STR}skillLevel")
_SKILL_YRS      = URIRef(f"{_CV_STR}skillYearsExperience")

# Publications
_BIBO_ARTICLE   = URIRef(f"{_BIBO}Article")
_BIBO_DOI       = URIRef(f"{_BIBO}doi")
_DCT_TITLE      = URIRef(f"{_DCT}title")
_DCT_CREATOR    = URIRef(f"{_DCT}creator")
_DCT_DATE       = URIRef(f"{_DCT}date")
_BIBO_VOLUME    = URIRef(f"{_BIBO}volume")
_BIBO_ISSUE     = URIRef(f"{_BIBO}issue")

# Education
_CV_EDUCATION   = URIRef(f"{_CV_STR}Education")
_CV_DEGREE      = URIRef(f"{_CV_STR}degreeType")
_CV_MAJOR       = URIRef(f"{_CV_STR}eduMajor")
_CV_INST        = URIRef(f"{_CV_STR}studiedIn")
_CV_GRAD_DATE   = URIRef(f"{_CV_STR}eduGradDate")

# Training & certifications
_CVX_TRAINING   = URIRef(f"{_CVX_STR}Training")
_CVX_TRAIN_TTL  = URIRef(f"{_CVX_STR}trainingTitle")
_CVX_PROV       = URIRef(f"{_CVX_STR}trainingProvider")
_CVX_TRAIN_DT   = URIRef(f"{_CVX_STR}trainingDate")
_CVX_CERT       = URIRef(f"{_CVX_STR}certificationName")
_CVX_CERT_DATE  = URIRef(f"{_CVX_STR}certificationDate")
_CVX_CERT_PROV  = URIRef(f"{_CVX_STR}certificationProvider")

# MOOCs
_CVX_MOOC       = URIRef(f"{_CVX_STR}MOOC")
_CVX_MOOC_TTL   = URIRef(f"{_CVX_STR}moocTitle")
_CVX_MOOC_PROV  = URIRef(f"{_CVX_STR}moocProvider")
_CVX_MOOC_DT    = URIRef(f"{_CVX_STR}moocCompletionDate")

# Projects (within-graph)
_CVX_PROJECT    = URIRef(f"{_CVX_STR}Project")
_CVX_PROJ_NAME  = URIRef(f"{_CVX_STR}projectName")
_CVX_PROJ_CLIENT = URIRef(f"{_CVX_STR}clientName")
_CVX_PROJ_START  = URIRef(f"{_CVX_STR}startDate")
_CVX_PROJ_END    = URIRef(f"{_CVX_STR}endDate")
_CVX_PROJ_BUDGET = URIRef(f"{_CVX_STR}projectBudget")
_CVX_PROJ_CAPEX  = URIRef(f"{_CVX_STR}capex")
_CVX_PROJ_ACT    = URIRef(f"{_CVX_STR}activitiesPerformed")
_CVX_PROJ_BEN    = URIRef(f"{_CVX_STR}benefitsDelivered")
_CVX_PROJ_DESC   = URIRef(f"{_CVX_STR}projectDescription")
_CVX_PROJ_DOMAIN = URIRef(f"{_CVX_STR}domain")
_CVX_PROJ_SKILL  = URIRef(f"{_CVX_STR}projectSkill")
_CV_SKILL        = URIRef(f"{_CV_STR}skill")

# Companies / employers (within-graph)
_CV_COMPANY     = URIRef(f"{_CV_STR}Company")
_CV_COMP_NAME   = URIRef(f"{_CV_STR}Name")

# Skill level ranking (higher → better)
_SKILL_LEVEL_RANK: dict[str, int] = {
    "expert": 5,
    "advanced": 4,
    "skilled": 3,
    "proficient": 3,
    "intermediate": 2,
    "beginner": 1,
    "basic": 1,
}

# Default similarity thresholds per section
DEFAULT_THRESHOLDS: dict[str, float] = {
    "skills":        0.75,   # normalised names; catches minor wording differences
    "publications":  0.88,
    "education":     0.85,
    "training":      0.80,   # title-primary (0.80 primary; provider/date secondary)
    "moocs":         0.88,
    "projects":      0.65,   # composite score: name + client + dates + amount
    "companies":     0.85,
}


@dataclass
class DeduplicationStats:
    """Per-section counts of duplicate nodes removed by :func:`deduplicate_graph`.

    The ``total`` property sums all section counts.
    """
    skills:        int = field(default=0)
    publications:  int = field(default=0)
    education:     int = field(default=0)
    training:      int = field(default=0)
    moocs:         int = field(default=0)
    projects:      int = field(default=0)
    companies:     int = field(default=0)

    @property
    def total(self) -> int:
        return (
            self.skills + self.publications + self.education
            + self.training + self.moocs + self.projects + self.companies
        )


# ── Low-level graph helpers ───────────────────────────────────────────────────

def _first_literal(g: Graph, subj: URIRef, pred: URIRef) -> str:
    for _, _, o in g.triples((subj, pred, None)):
        if isinstance(o, Literal):
            return str(o).strip()
    return ""


def _first_str(g: Graph, subj: URIRef, pred: URIRef) -> str:
    """First object as string regardless of type (literal or IRI)."""
    for _, _, o in g.triples((subj, pred, None)):
        return str(o).strip()
    return ""


def _first_int(g: Graph, subj: URIRef, pred: URIRef) -> int:
    val = _first_literal(g, subj, pred)
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _triple_count(g: Graph, subj: URIRef) -> int:
    return sum(1 for _ in g.triples((subj, None, None)))


def _replace_iri_refs(g: Graph, old: URIRef, new: URIRef) -> None:
    """Rewrite every triple that uses *old* as an object to use *new*."""
    for s, p, _ in list(g.triples((None, None, old))):
        g.remove((s, p, old))
        g.add((s, p, new))


def _remove_subject(g: Graph, node: URIRef) -> None:
    """Delete all triples where *node* is the subject."""
    for triple in list(g.triples((node, None, None))):
        g.remove(triple)


def _absorb_node(g: Graph, winner: URIRef, loser: URIRef) -> None:
    """Merge *loser* into *winner*: copy unique properties, redirect refs, delete *loser*."""
    for _, p, o in list(g.triples((loser, None, None))):
        if not list(g.triples((winner, p, None))):
            g.add((winner, p, o))
    _replace_iri_refs(g, loser, winner)
    _remove_subject(g, loser)


def _richest(g: Graph, node_a: URIRef, node_b: URIRef) -> tuple[URIRef, URIRef]:
    """Return (winner, loser) where the winner has more triples."""
    return (node_a, node_b) if _triple_count(g, node_a) >= _triple_count(g, node_b) \
        else (node_b, node_a)


# ── Text normalisation ────────────────────────────────────────────────────────

# Regex that matches all Unicode dash/hyphen variants
_DASH_RE = re.compile(
    r"[-­‐‑‒–—―−﹘﹣－]"
)
_PUNC_RE = re.compile(r"[^\w\s\-]")
_WS_RE   = re.compile(r"\s+")

# Acronym expansions applied during normalisation (cert/training titles)
_ACRONYM_MAP: dict[str, str] = {
    "pmp":    "project management professional",
    "pmi":    "project management institute",
    "aws":    "amazon web services",
    "azure":  "microsoft azure",
    "gcp":    "google cloud platform",
    "cissp":  "certified information systems security professional",
    "cisa":   "certified information systems auditor",
    "cism":   "certified information security manager",
    "itil":   "information technology infrastructure library",
    "prince2": "projects in controlled environments",
    "csm":    "certified scrum master",
    "cfa":    "chartered financial analyst",
    "cpa":    "certified public accountant",
    "mba":    "master of business administration",
    "agile":  "agile",
    "lean":   "lean",
    "six":    "six",   # avoid over-expanding "six sigma"
}


def _normalise_text(s: str) -> str:
    """Normalise text for robust similarity comparison.

    Applies (in order): lowercase, Unicode dash normalisation to ``-``,
    punctuation stripping (keeps hyphens and word characters), whitespace
    collapse, and acronym expansion on isolated tokens.
    """
    s = s.strip().lower()
    s = _DASH_RE.sub("-", s)
    s = _PUNC_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    words = [_ACRONYM_MAP.get(w.strip("-"), w) for w in s.split()]
    return " ".join(words)


# ── Amount extraction (for project budget / CAPEX matching) ──────────────────

_AMOUNT_RE = re.compile(
    r"(?:[€$£]|eur?|usd?|gbp?)?\s*([\d,]+(?:\.\d+)?)\s*"
    r"(k|m|b|bn|million|billion|thousand)?",
    re.IGNORECASE,
)
_AMOUNT_SCALE: dict[str, float] = {
    "k": 1_000,        "thousand": 1_000,
    "m": 1_000_000,    "million":  1_000_000,
    "b": 1_000_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000,
}


def _extract_amount(s: str) -> float | None:
    """Return a numeric value parsed from a budget/CAPEX string, or ``None``."""
    m = _AMOUNT_RE.search(s)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    scale = _AMOUNT_SCALE.get((m.group(2) or "").lower(), 1.0)
    return num * scale


# ── Date-range overlap (for project date matching) ────────────────────────────

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parse_year(s: str) -> int | None:
    """Extract the first four-digit year from *s*, or ``None``."""
    m = _YEAR_RE.search(s)
    return int(m.group(0)) if m else None


def _date_overlap_score(start_a: str, end_a: str, start_b: str, end_b: str) -> float:
    """Return an overlap score in ``[0.0, 1.0]`` for two year-based date ranges.

    Returns ``0.5`` (neutral) when not enough date information is available so
    that missing dates neither help nor hurt the composite score.

    Returns ``1.0`` for a genuine overlap, ``0.3`` when ranges are adjacent
    (one year apart), ``0.0`` when they do not overlap.
    """
    ya_s = _parse_year(start_a)
    ya_e = _parse_year(end_a) or ya_s
    yb_s = _parse_year(start_b)
    yb_e = _parse_year(end_b) or yb_s

    # Not enough info — neutral
    if not any([ya_s, ya_e, yb_s, yb_e]):
        return 0.5

    # Fill gaps: single-date projects
    ya_s = ya_s or ya_e
    ya_e = ya_e or ya_s
    yb_s = yb_s or yb_e
    yb_e = yb_e or yb_s

    if not (ya_s and yb_s):
        return 0.5

    if ya_s <= yb_e and yb_s <= ya_e:
        return 1.0
    gap = min(abs(ya_s - yb_e), abs(yb_s - ya_e))
    return 0.3 if gap == 1 else 0.0


# ── Project composite score ───────────────────────────────────────────────────

def _project_composite_score(
    g: Graph, node_a: URIRef, node_b: URIRef
) -> tuple[float, dict[str, float | None]]:
    """Return a weighted composite similarity score for two project nodes.

    The score combines four signals:

    * **Name** (weight 0.40) — normalised name fuzzy similarity.
    * **Client** (weight 0.30) — normalised client-name fuzzy similarity;
      only counted when both nodes carry a client name.
    * **Date overlap** (weight 0.20) — year-range overlap score;
      only counted when at least one node has a date.
    * **Budget / CAPEX** (weight 0.10) — 1.0 if amounts are within 20% of
      each other, 0.0 otherwise; only counted when both nodes have an amount.

    Each signal is included only when the required fields are available, and the
    final score is normalised by the total weight of applied signals.

    Returns
    -------
    tuple of (composite_score, detail_dict) where detail_dict contains
    "name", "client", "dates", "capex" as individual scores (``None`` when
    the signal was not applied).
    """
    name_a   = _normalise_text(_first_literal(g, node_a, _CVX_PROJ_NAME))
    name_b   = _normalise_text(_first_literal(g, node_b, _CVX_PROJ_NAME))
    client_a = _normalise_text(_first_literal(g, node_a, _CVX_PROJ_CLIENT))
    client_b = _normalise_text(_first_literal(g, node_b, _CVX_PROJ_CLIENT))
    start_a  = _first_literal(g, node_a, _CVX_PROJ_START)
    end_a    = _first_literal(g, node_a, _CVX_PROJ_END)
    start_b  = _first_literal(g, node_b, _CVX_PROJ_START)
    end_b    = _first_literal(g, node_b, _CVX_PROJ_END)
    budget_a = (_first_literal(g, node_a, _CVX_PROJ_BUDGET)
                or _first_literal(g, node_a, _CVX_PROJ_CAPEX))
    budget_b = (_first_literal(g, node_b, _CVX_PROJ_BUDGET)
                or _first_literal(g, node_b, _CVX_PROJ_CAPEX))

    score  = 0.0
    weight = 0.0
    name_sig:   float | None = None
    client_sig: float | None = None
    dates_sig:  float | None = None
    capex_sig:  float | None = None

    # Name (always included)
    name_sig = _similarity(name_a, name_b) if name_a and name_b else 0.0
    score  += 0.40 * name_sig
    weight += 0.40

    # Client
    if client_a and client_b:
        client_sig = _similarity(client_a, client_b)
        score  += 0.30 * client_sig
        weight += 0.30

    # Date overlap
    if any([start_a, end_a, start_b, end_b]):
        dates_sig = _date_overlap_score(start_a, end_a, start_b, end_b)
        score  += 0.20 * dates_sig
        weight += 0.20

    # Budget / CAPEX
    amt_a = _extract_amount(budget_a) if budget_a else None
    amt_b = _extract_amount(budget_b) if budget_b else None
    if amt_a is not None and amt_b is not None and max(amt_a, amt_b) > 0:
        ratio = min(amt_a, amt_b) / max(amt_a, amt_b)
        capex_sig = 1.0 if ratio >= 0.80 else 0.0
        score  += 0.10 * capex_sig
        weight += 0.10

    composite = score / weight if weight > 0 else 0.0
    detail: dict[str, float | None] = {
        "name":   name_sig,
        "client": client_sig,
        "dates":  dates_sig,
        "capex":  capex_sig,
    }
    return composite, detail


# ── Union merge for projects (multi-valued fields get union, not winner-only) ─

_UNION_PREDS: frozenset[URIRef] = frozenset({
    _CVX_PROJ_ACT,
    _CVX_PROJ_BEN,
    _CVX_PROJ_DESC,
    _CVX_PROJ_DOMAIN,
    _CVX_PROJ_SKILL,
    _CV_SKILL,
})


def _union_absorb_node(g: Graph, winner: URIRef, loser: URIRef) -> None:
    """Merge *loser* into *winner* with union semantics for multi-valued fields.

    For predicates in :data:`_UNION_PREDS` (activities, benefits, descriptions,
    domains, skills), *all* values from *loser* that are not already on *winner*
    are added — accumulating the full information from both nodes.  For all other
    predicates, the winner's existing value is kept (first-write wins).
    """
    winner_vals: dict[URIRef, set[str]] = {}
    for _, p, o in g.triples((winner, None, None)):
        winner_vals.setdefault(p, set()).add(str(o))

    for _, p, o in list(g.triples((loser, None, None))):
        if p in _UNION_PREDS:
            if str(o) not in winner_vals.get(p, set()):
                g.add((winner, p, o))
                winner_vals.setdefault(p, set()).add(str(o))
        elif p not in winner_vals:
            g.add((winner, p, o))
            winner_vals[p] = {str(o)}

    _replace_iri_refs(g, loser, winner)
    _remove_subject(g, loser)


# ── Section-specific dedup functions ─────────────────────────────────────────

def dedup_skills(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["skills"],
    verbose: bool = False,
) -> int:
    """Deduplicate skill nodes within *g*; return count removed.

    Duplicate detection: normalised ``cv:skillName`` string similarity >= *threshold*.
    Normalisation (lowercase, dash-normalise, punctuation strip) is applied before
    fuzzy comparison so that ``"React.js"`` / ``"ReactJS"`` and
    ``"Machine Learning"`` / ``"machine learning"`` are correctly matched.

    Winner selection priority:
    1. Highest skill level (Expert > Advanced > Skilled/Proficient > Intermediate > Beginner/Basic).
    2. Most years of experience.
    3. Longer original name (more specific).

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Similarity threshold on normalised names (default 0.75).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate skill nodes removed.
    """
    skills = [s for s, _, _ in g.triples((None, _SKILL_NAME, None)) if isinstance(s, URIRef)]
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(skills):
        if node_a in merged_away:
            continue
        raw_a  = _first_literal(g, node_a, _SKILL_NAME)
        norm_a = _normalise_text(raw_a)
        for node_b in skills[i + 1:]:
            if node_b in merged_away:
                continue
            raw_b  = _first_literal(g, node_b, _SKILL_NAME)
            norm_b = _normalise_text(raw_b)
            sim = _similarity(norm_a, norm_b)
            if not norm_a or not norm_b or sim < threshold:
                continue
            rank_a = _SKILL_LEVEL_RANK.get(_first_literal(g, node_a, _SKILL_LVL).lower(), 0)
            rank_b = _SKILL_LEVEL_RANK.get(_first_literal(g, node_b, _SKILL_LVL).lower(), 0)
            yrs_a  = _first_int(g, node_a, _SKILL_YRS)
            yrs_b  = _first_int(g, node_b, _SKILL_YRS)
            a_wins = (
                rank_a > rank_b
                or (rank_a == rank_b and yrs_a > yrs_b)
                or (rank_a == rank_b and yrs_a == yrs_b and len(raw_a) >= len(raw_b))
            )
            winner, loser = (node_a, node_b) if a_wins else (node_b, node_a)
            if verbose:
                w_lvl = _first_literal(g, winner, _SKILL_LVL)
                w_yrs = _first_int(g, winner, _SKILL_YRS)
                raw_w = raw_a if winner == node_a else raw_b
                detail = ", ".join(filter(None, [w_lvl or "", f"{w_yrs}yr" if w_yrs else ""]))
                print(f"[dedup:skills]   MATCH  {raw_a!r} ~ {raw_b!r}  sim={sim:.2f}"
                      f"  → keep {raw_w!r} ({detail})  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_publications(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["publications"],
    verbose: bool = False,
) -> int:
    """Deduplicate publication nodes within *g*; return count removed.

    Duplicate detection: exact DOI match *or* ``dcterms:title`` similarity >= *threshold*.
    Winner: node with more triples (richer record).

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Title similarity threshold (default 0.88).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate publication nodes removed.
    """
    pubs: list[URIRef] = [
        s for s, _, _ in g.triples((None, _RDF_TYPE, _BIBO_ARTICLE)) if isinstance(s, URIRef)
    ]
    for s, _, _ in g.triples((None, _DCT_TITLE, None)):
        if isinstance(s, URIRef) and s not in pubs:
            pubs.append(s)
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(pubs):
        if node_a in merged_away:
            continue
        doi_a   = _first_literal(g, node_a, _BIBO_DOI).lower()
        title_a = _first_literal(g, node_a, _DCT_TITLE)
        for node_b in pubs[i + 1:]:
            if node_b in merged_away:
                continue
            doi_b   = _first_literal(g, node_b, _BIBO_DOI).lower()
            title_b = _first_literal(g, node_b, _DCT_TITLE)
            doi_match   = bool(doi_a and doi_b and doi_a == doi_b)
            title_sim   = _similarity(title_a, title_b) if title_a and title_b else 0.0
            title_match = title_sim >= threshold
            if not (doi_match or title_match):
                continue
            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                how = "doi=exact" if doi_match else f"title_sim={title_sim:.2f}"
                print(f"[dedup:publications]  MATCH  {title_a!r} ~ {title_b!r}  {how}"
                      f"  → keep <{winner}>  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_education(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["education"],
    verbose: bool = False,
) -> int:
    """Deduplicate education nodes within *g*; return count removed.

    Duplicate detection: similarity of the composite key
    ``(degreeType, eduMajor, studiedIn)`` >= *threshold*.
    Winner: node with more triples.

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Key similarity threshold (default 0.85).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate education nodes removed.
    """
    edu_nodes = [
        s for s, _, _ in g.triples((None, _RDF_TYPE, _CV_EDUCATION)) if isinstance(s, URIRef)
    ]
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(edu_nodes):
        if node_a in merged_away:
            continue
        key_a = " ".join([
            _first_literal(g, node_a, _CV_DEGREE),
            _first_literal(g, node_a, _CV_MAJOR),
            _first_str(g, node_a, _CV_INST),
        ]).strip()
        for node_b in edu_nodes[i + 1:]:
            if node_b in merged_away:
                continue
            key_b = " ".join([
                _first_literal(g, node_b, _CV_DEGREE),
                _first_literal(g, node_b, _CV_MAJOR),
                _first_str(g, node_b, _CV_INST),
            ]).strip()
            sim = _similarity(key_a, key_b)
            if not key_a or not key_b or sim < threshold:
                continue
            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                print(f"[dedup:education]  MATCH  {key_a!r} ~ {key_b!r}  sim={sim:.2f}"
                      f"  → keep <{winner}>  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_training(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["training"],
    verbose: bool = False,
) -> int:
    """Deduplicate training and certification nodes within *g*; return count removed.

    Matching strategy (title-primary, provider/date secondary):

    * Title and provider names are normalised before comparison (lowercase,
      dash-normalise, punctuation strip, common acronym expansion).
    * **Strong title match** (normalised title similarity >= *threshold*):
      always treated as a duplicate, regardless of provider or date.
    * **Weaker title match** (``threshold - 0.15`` ≤ title sim < *threshold*):
      treated as a duplicate only when the normalised provider also matches
      (similarity >= 0.70).  Date is used as an optional tiebreaker but is
      never required.
    * ``certificationName`` is used as the title fallback when ``trainingTitle``
      is absent.

    Winner: node with more triples (richer record).

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Primary title similarity threshold (default 0.80).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate training/certification nodes removed.
    """
    nodes: list[URIRef] = [
        s for s, _, _ in g.triples((None, _RDF_TYPE, _CVX_TRAINING)) if isinstance(s, URIRef)
    ]
    for s, _, _ in g.triples((None, _CVX_CERT, None)):
        if isinstance(s, URIRef) and s not in nodes:
            nodes.append(s)
    merged_away: set[URIRef] = set()
    removed = 0
    soft_threshold = max(0.0, threshold - 0.15)

    for i, node_a in enumerate(nodes):
        if node_a in merged_away:
            continue
        raw_title_a = (
            _first_literal(g, node_a, _CVX_TRAIN_TTL)
            or _first_literal(g, node_a, _CVX_CERT)
        )
        raw_prov_a = (
            _first_literal(g, node_a, _CVX_PROV)
            or _first_literal(g, node_a, _CVX_CERT_PROV)
        )
        title_a = _normalise_text(raw_title_a)
        prov_a  = _normalise_text(raw_prov_a)

        for node_b in nodes[i + 1:]:
            if node_b in merged_away:
                continue
            raw_title_b = (
                _first_literal(g, node_b, _CVX_TRAIN_TTL)
                or _first_literal(g, node_b, _CVX_CERT)
            )
            raw_prov_b = (
                _first_literal(g, node_b, _CVX_PROV)
                or _first_literal(g, node_b, _CVX_CERT_PROV)
            )
            title_b = _normalise_text(raw_title_b)
            prov_b  = _normalise_text(raw_prov_b)

            if not title_a or not title_b:
                continue

            title_sim = _similarity(title_a, title_b)
            prov_sim: float | None = None
            tier = ""

            if title_sim >= threshold:
                tier = "tier-1"
            elif title_sim >= soft_threshold:
                if not prov_a or not prov_b:
                    continue
                prov_sim = _similarity(prov_a, prov_b)
                if prov_sim < 0.70:
                    continue
                tier = f"tier-2, prov={prov_sim:.2f}"
            else:
                continue

            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                print(f"[dedup:training]  MATCH  title_sim={title_sim:.2f} [{tier}]"
                      f"  {raw_title_a!r} ~ {raw_title_b!r}"
                      f"  → keep <{winner}>  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_moocs(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["moocs"],
    verbose: bool = False,
) -> int:
    """Deduplicate MOOC nodes within *g*; return count removed.

    Duplicate detection: similarity of ``(provider, title)`` key >= *threshold*.
    Winner: node with more triples.

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Key similarity threshold (default 0.88).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate MOOC nodes removed.
    """
    nodes: list[URIRef] = [
        s for s, _, _ in g.triples((None, _RDF_TYPE, _CVX_MOOC)) if isinstance(s, URIRef)
    ]
    # Also catch MOOC-like nodes labelled by moocTitle without explicit type
    for s, _, _ in g.triples((None, _CVX_MOOC_TTL, None)):
        if isinstance(s, URIRef) and s not in nodes:
            nodes.append(s)
    if not nodes:
        return 0
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(nodes):
        if node_a in merged_away:
            continue
        key_a = " ".join([
            _first_literal(g, node_a, _CVX_MOOC_PROV),
            _first_literal(g, node_a, _CVX_MOOC_TTL),
        ]).strip()
        for node_b in nodes[i + 1:]:
            if node_b in merged_away:
                continue
            key_b = " ".join([
                _first_literal(g, node_b, _CVX_MOOC_PROV),
                _first_literal(g, node_b, _CVX_MOOC_TTL),
            ]).strip()
            sim = _similarity(key_a, key_b)
            if not key_a or not key_b or sim < threshold:
                continue
            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                print(f"[dedup:moocs]  MATCH  {key_a!r} ~ {key_b!r}  sim={sim:.2f}"
                      f"  → keep <{winner}>  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_projects(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["projects"],
    verbose: bool = False,
) -> int:
    """Deduplicate project nodes within a *single* graph using multi-field composite scoring.

    Intended for within-graph duplicates only (e.g. two sections of the same
    CV describe the same project differently).  Cross-file reconciliation is
    handled by :func:`reconcile_interactive`.

    Composite score weights:

    * **Name** (0.40) — normalised project-name fuzzy similarity; always included.
    * **Client** (0.30) — normalised client-name fuzzy similarity; included only
      when *both* nodes carry a client name.
    * **Date overlap** (0.20) — year-range overlap score; included when at least
      one node has a start or end date.
    * **Budget / CAPEX** (0.10) — 1.0 if parsed amounts are within 20% of each
      other, 0.0 otherwise; included when both nodes carry an amount.

    The composite score is normalised by the total weight of applied signals, so
    a pair with no client or date data is still evaluated fairly on name alone.
    A pair with strongly matching client + dates can be flagged as a duplicate
    even when the project names differ significantly.

    On merge, multi-valued project fields (activities, benefits, descriptions,
    domains, skills) are *unioned* rather than winner-takes-all, so no
    information is lost.  Winner is the node with more triples.

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Composite score threshold (default 0.65).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate project nodes removed.
    """
    nodes: list[URIRef] = []
    for s, _, _ in g.triples((None, _RDF_TYPE, _CVX_PROJECT)):
        if isinstance(s, URIRef):
            nodes.append(s)
    for s, _, _ in g.triples((None, _CVX_PROJ_NAME, None)):
        if isinstance(s, URIRef) and s not in nodes:
            nodes.append(s)
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(nodes):
        if node_a in merged_away:
            continue
        for node_b in nodes[i + 1:]:
            if node_b in merged_away:
                continue
            composite, detail = _project_composite_score(g, node_a, node_b)
            if composite < threshold:
                continue
            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                def _fs(v: float | None) -> str:
                    return f"{v:.2f}" if v is not None else "—"
                name_a_str = _first_literal(g, node_a, _CVX_PROJ_NAME)
                name_b_str = _first_literal(g, node_b, _CVX_PROJ_NAME)
                breakdown = (
                    f"name={_fs(detail['name'])} client={_fs(detail['client'])}"
                    f" dates={_fs(detail['dates'])} capex={_fs(detail['capex'])}"
                )
                w_triples  = _triple_count(g, winner)
                print(f"[dedup:projects]  MATCH  composite={composite:.2f} [{breakdown}]"
                      f"  {name_a_str!r} ~ {name_b_str!r}"
                      f"  → union-merge <{winner}> ({w_triples} triples)  | drop <{loser}>")
            _union_absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def dedup_companies(
    g: Graph,
    threshold: float = DEFAULT_THRESHOLDS["companies"],
    verbose: bool = False,
) -> int:
    """Deduplicate company/employer nodes within a *single* graph.

    Duplicate detection: ``cv:Name`` similarity >= *threshold*.
    Winner: node with more triples.

    Args:
        g: In-place rdflib Graph to deduplicate.
        threshold: Name similarity threshold (default 0.85).
        verbose: If ``True``, print a log line for every merge decision.

    Returns:
        Number of duplicate company nodes removed.
    """
    nodes: list[URIRef] = []
    for s, _, _ in g.triples((None, _RDF_TYPE, _CV_COMPANY)):
        if isinstance(s, URIRef):
            nodes.append(s)
    for s, _, _ in g.triples((None, _CV_COMP_NAME, None)):
        if isinstance(s, URIRef) and s not in nodes:
            nodes.append(s)
    merged_away: set[URIRef] = set()
    removed = 0
    for i, node_a in enumerate(nodes):
        if node_a in merged_away:
            continue
        name_a = _first_literal(g, node_a, _CV_COMP_NAME)
        for node_b in nodes[i + 1:]:
            if node_b in merged_away:
                continue
            name_b = _first_literal(g, node_b, _CV_COMP_NAME)
            sim = _similarity(name_a, name_b)
            if not name_a or not name_b or sim < threshold:
                continue
            winner, loser = _richest(g, node_a, node_b)
            if verbose:
                print(f"[dedup:companies]  MATCH  {name_a!r} ~ {name_b!r}  sim={sim:.2f}"
                      f"  → keep <{winner}>  | drop <{loser}>")
            _absorb_node(g, winner, loser)
            merged_away.add(loser)
            removed += 1
    return removed


def deduplicate_graph(
    g: Graph,
    thresholds: dict[str, float] | None = None,
    verbose: bool = False,
) -> DeduplicationStats:
    """Run all section-aware deduplication passes on *g* in-place.

    Each pass targets a specific CV section and applies section-specific
    matching logic and winner-selection rules.  Passes are run in dependency
    order so that company and project merges happen before skill merges (which
    may reference them).

    Sections covered:

    +------------------+------------------------------------------+----------+
    | Section          | Match key                                | Default  |
    |                  |                                          | threshold|
    +==================+==========================================+==========+
    | Skills           | ``cv:skillName`` fuzzy match             | 0.75     |
    +------------------+------------------------------------------+----------+
    | Publications     | ``bibo:doi`` exact or ``dcterms:title``  | 0.88     |
    |                  | fuzzy match                              |          |
    +------------------+------------------------------------------+----------+
    | Education        | (degreeType, eduMajor, studiedIn) key    | 0.85     |
    +------------------+------------------------------------------+----------+
    | Training / certs | title-primary, provider secondary        | 0.80     |
    +------------------+------------------------------------------+----------+
    | MOOCs            | (provider, title) key                    | 0.88     |
    +------------------+------------------------------------------+----------+
    | Projects         | composite: name+client+dates+budget      | 0.65     |
    +------------------+------------------------------------------+----------+
    | Companies        | ``cv:Name`` fuzzy match                  | 0.85     |
    +------------------+------------------------------------------+----------+

    Args:
        g: rdflib :class:`~rdflib.Graph` to deduplicate in-place.
        thresholds: Optional overrides for per-section similarity thresholds.
            Keys match the section names in :data:`DEFAULT_THRESHOLDS`
            (``"skills"``, ``"publications"``, etc.).  Only the keys you
            provide are overridden; others keep their defaults.
        verbose: If ``True``, print a structured log line for every merge
            decision and a summary at the end.

    Returns:
        :class:`DeduplicationStats` with per-section counts of removed nodes.

    Example::

        from rdflib import Graph
        from resume_rdf.reconcile import deduplicate_graph

        g = Graph()
        g.parse("merged.ttl", format="turtle")
        stats = deduplicate_graph(g, thresholds={"skills": 0.85}, verbose=True)
        print(f"Removed {stats.total} duplicate nodes")
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    stats = DeduplicationStats(
        companies    = dedup_companies(g,    threshold=t["companies"],    verbose=verbose),
        projects     = dedup_projects(g,     threshold=t["projects"],     verbose=verbose),
        skills       = dedup_skills(g,       threshold=t["skills"],       verbose=verbose),
        publications = dedup_publications(g, threshold=t["publications"], verbose=verbose),
        education    = dedup_education(g,    threshold=t["education"],    verbose=verbose),
        training     = dedup_training(g,     threshold=t["training"],     verbose=verbose),
        moocs        = dedup_moocs(g,        threshold=t["moocs"],        verbose=verbose),
    )
    if verbose:
        print(
            f"[dedup] SUMMARY"
            f"  skills:{stats.skills}"
            f"  publications:{stats.publications}"
            f"  education:{stats.education}"
            f"  training:{stats.training}"
            f"  moocs:{stats.moocs}"
            f"  projects:{stats.projects}"
            f"  companies:{stats.companies}"
            f"  total:{stats.total}"
        )
    return stats


def reconcile_interactive(
    ttl_files: list[Path],
    threshold: float = 0.75,
    dry_run: bool = False,
    auto_yes: bool = False,
) -> int:
    """Run interactive entity reconciliation across a set of Turtle files.

    Presents each candidate duplicate pair to the user on the terminal and
    collects a yes/no/quit response.  Confirmed merges are accumulated into a
    mapping, then applied to all files in one pass at the end.

    The IRI from the **first file listed** (by argument order) is kept as the
    canonical IRI; the other is replaced everywhere.  Re-order the file
    arguments to control which IRI wins.

    Args:
        ttl_files:  Ordered list of Turtle file paths to reconcile.
        threshold:  Minimum similarity score (``0``–``1``) to surface a pair.
                    Defaults to ``0.75``.
        dry_run:    If ``True``, report what would be done but don't write any
                    files.  Defaults to ``False``.
        auto_yes:   If ``True``, confirm all matches above *threshold*
                    automatically (non-interactive batch mode).
                    Defaults to ``False``.

    Returns:
        Number of merges confirmed (and applied, unless *dry_run* is set).

    Example::

        from pathlib import Path
        from resume_rdf.reconcile import reconcile_interactive

        n = reconcile_interactive(
            [Path("alice.ttl"), Path("bob.ttl")],
            threshold=0.80,
        )
    """
    if not ttl_files:
        print("No TTL files provided.")
        return 0

    print(f"Loading {len(ttl_files)} file(s)…")
    entities = load_entities(ttl_files)
    print(f"  Extracted {len(entities)} entities "
          f"({sum(1 for e in entities if e.kind == 'project')} projects, "
          f"{sum(1 for e in entities if e.kind == 'company')} companies).")

    matches = find_matches(entities, threshold=threshold)
    if not matches:
        print(f"No candidate duplicates found (threshold={threshold:.0%}).")
        return 0

    print(f"\nFound {len(matches)} candidate pair(s) at ≥{threshold:.0%} similarity:\n")

    # IRI → canonical IRI; built up as user confirms matches
    mapping: dict[URIRef, URIRef] = {}
    confirmed = 0

    for idx, match in enumerate(matches, 1):
        a, b = match.a, match.b

        # Resolve through any already-confirmed merges
        canon_a = mapping.get(a.iri, a.iri)
        canon_b = mapping.get(b.iri, b.iri)
        if canon_a == canon_b:
            continue  # already unified by a prior merge

        print(f"── [{idx}/{len(matches)}]  {match.kind.upper()}  "
              f"(similarity {match.score:.0%}) ──")
        print(f"  A: {a.label!r:<45} {a.iri}")
        print(f"     ({a.source.name})")
        print(f"  B: {b.label!r:<45} {b.iri}")
        print(f"     ({b.source.name})")
        print(f"  Canonical if merged → A  ({canon_a})")

        if auto_yes:
            answer = "y"
            print("  [auto-yes]")
        else:
            try:
                answer = input("  Same entity? [y/n/q(uit)] ").strip().lower()
            except EOFError:
                answer = "n"

        if answer.startswith("q"):
            print("Aborted.")
            break

        if answer == "y":
            mapping[canon_b] = canon_a
            confirmed += 1
            print(f"  ✓ Will rewrite  {canon_b}  →  {canon_a}")
        print()

    if confirmed == 0:
        print("No merges confirmed.")
        return 0

    if dry_run:
        print(f"Dry run: {confirmed} merge(s) identified, no files written.")
        return confirmed

    print(f"Applying {confirmed} merge(s) across {len(ttl_files)} file(s)…")
    results = apply_mapping(ttl_files, mapping)
    if results:
        for path, count in sorted(results.items()):
            print(f"  {path.name}: {count} triple(s) rewritten")
    else:
        print("  No triples needed rewriting (entities may only appear in one file).")
    print("Done.")
    return confirmed


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """CLI entry-point for ``cv-reconcile``.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).  Useful for
            testing without spawning a subprocess.
    """
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
        prog="cv-reconcile",
        description="Reconcile entities across multiple Turtle RDF CV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              cv-reconcile alice.ttl bob.ttl
              cv-reconcile *.ttl --threshold 0.80
              cv-reconcile alice.ttl bob.ttl --dry-run
              cv-reconcile alice.ttl bob.ttl --yes

            Notes
            -----
            The IRI from the first file listed is kept as canonical when two
            entities are merged.  Re-order the arguments to choose which IRI wins.

            Requires rdflib:  pip install rdflib
        """),
    )
    parser.add_argument(
        "ttl_files",
        nargs="+",
        metavar="FILE.ttl",
        help="Two or more Turtle RDF files to reconcile.",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.75,
        metavar="SCORE",
        help="Minimum similarity score to surface a pair (default: 0.75).",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show matches but do not rewrite any files.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Accept all matches above threshold automatically.",
    )

    args = parser.parse_args(argv)
    paths = [Path(p) for p in args.ttl_files]

    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    if len(paths) < 2:
        print("Error: provide at least two TTL files to compare.", file=sys.stderr)
        sys.exit(1)

    reconcile_interactive(
        paths,
        threshold=args.threshold,
        dry_run=args.dry_run,
        auto_yes=args.yes,
    )


if __name__ == "__main__":
    main()
