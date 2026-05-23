"""
resume_rdf
==========
Parse CVs into Turtle RDF knowledge graphs using the Anthropic Claude API.

Quick start::

    from resume_rdf import generate_graph_from_file

    turtle, usage = generate_graph_from_file(
        "my_cv.pdf",
        api_key="sk-ant-...",
        extra_context="Energy sector, English labels.",
    )
    print(turtle)

Modules
-------
api         generate_graph_from_file / generate_graph_from_bytes
cache       file-based SHA-256 response cache (used by api and merge)
cli         cv-to-rdf command-line entry-point
data        dataset download, load_records, iter_records
export      ttl_to_markdown  (cv-to-md CLI)
merge       consolidate_ttls — same-person TTL merger  (cv-merge CLI)
ontology    SYSTEM_PROMPT + NAMESPACES constants
parsing     count_triples, extract_person_name, validate_turtle
qa          audit_experience, update_field  (cv-audit / cv-update CLIs)
reconcile   load_entities, find_matches, reconcile_interactive  (cv-reconcile CLI)
viz         visualize_cv  (cv-graph CLI)
"""

from resume_rdf.api import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    generate_graph_from_bytes,
    generate_graph_from_file,
)
from resume_rdf.data import (
    DATASET_REPO,
    DATASET_URL,
    download_dataset,
    iter_records,
    load_records,
)
from resume_rdf.ontology import NAMESPACES, SYSTEM_PROMPT
from resume_rdf.reconcile import (
    Entity,
    Match,
    apply_mapping,
    find_matches,
    load_entities,
    reconcile_interactive,
)
from resume_rdf.parsing import (
    count_triples,
    extract_person_name,
    validate_turtle,
)
from resume_rdf.qa import (
    Question,
    audit_experience,
    update_field,
)
from resume_rdf.viz import visualize_cv
from resume_rdf.export import ttl_to_markdown
from resume_rdf.merge import (
    MergeStats,
    consolidate_ttls,
)

__version__ = "0.1.0"
__all__ = [
    # generation
    "generate_graph_from_file",
    "generate_graph_from_bytes",
    # helpers
    "count_triples",
    "extract_person_name",
    "validate_turtle",
    # ontology
    "SYSTEM_PROMPT",
    "NAMESPACES",
    # defaults
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    # dataset
    "download_dataset",
    "iter_records",
    "load_records",
    "DATASET_REPO",
    "DATASET_URL",
    # reconciliation
    "reconcile_interactive",
    "load_entities",
    "find_matches",
    "apply_mapping",
    "Entity",
    "Match",
    # CV quality audit
    "audit_experience",
    "update_field",
    "Question",
    # visualisation
    "visualize_cv",
    # export
    "ttl_to_markdown",
    # merge / consolidation
    "consolidate_ttls",
    "MergeStats",
]
