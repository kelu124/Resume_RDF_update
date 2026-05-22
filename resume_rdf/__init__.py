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

The library exposes two generation functions, utility helpers, the ontology
constants used by the parser, dataset access utilities, and a cross-TTL
entity reconciler.
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
]
