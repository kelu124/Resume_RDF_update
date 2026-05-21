"""
cv_to_knowledge_graph.py
========================
Parse a CV (PDF or plain text) into a Turtle RDF knowledge graph using the
Anthropic Claude API.

The ontology used combines:
  cv:    ResumeRDF core    http://purl.org/captsolo/resume-rdf/0.2/cv#
  cvb:   ResumeRDF base    http://purl.org/captsolo/resume-rdf/0.2/base#
  cvx:   Custom extension  http://example.org/cv-extension#
  foaf:  FOAF              http://xmlns.com/foaf/0.1/
  bibo:  Bibliographic     http://purl.org/ontology/bibo/
  dcterms: Dublin Core     http://purl.org/dc/terms/
  xsd:   XML Schema        http://www.w3.org/2001/XMLSchema#

Node types extracted
--------------------
  foaf:Person / cv:CV          — identity and CV root
  cv:WorkHistory / cv:Company  — employment history
  cvx:Project                  — client engagements (role, activities, benefits, domain)
  cv:Skill                     — skills
  cv:Education                 — formal degrees
  cvx:MOOC                     — online courses (Coursera, edX, Udemy, ...)
  cvx:Training                 — workshops, certifications, bootcamps
  cvx:PersonalProject          — open-source / side projects / hardware
  bibo:AcademicArticle / ...   — publications (papers, reports, patents, articles)

Requirements
------------
  pip install anthropic
  pip install rdflib          # optional — only needed for --validate

API key
-------
  1. Sign up / log in at  https://console.anthropic.com
  2. Go to               https://console.anthropic.com/settings/keys
  3. Click "Create Key", copy the sk-ant-... string.
  Then either:
    export ANTHROPIC_API_KEY="sk-ant-..."   (recommended)
  or pass it with  --api-key sk-ant-...

Usage
-----
  # Basic — writes <stem>.ttl next to the input file
  python cv_to_knowledge_graph.py my_cv.pdf

  # Specify output path
  python cv_to_knowledge_graph.py my_cv.pdf --output graph.ttl

  # Provide extra context to help the parser
  python cv_to_knowledge_graph.py my_cv.pdf \\
      --context "I work mainly in energy and transport. Output labels in English."

  # Validate the output Turtle with rdflib
  python cv_to_knowledge_graph.py my_cv.pdf --validate

  # Use a different model (default: claude-sonnet-4-6)
  python cv_to_knowledge_graph.py my_cv.pdf --model claude-opus-4-6

  # Increase token budget for very long CVs (default: 60000)
  python cv_to_knowledge_graph.py my_cv.pdf --max-tokens 60000
"""

import argparse
import base64
import os
import re
import sys
import textwrap

import anthropic


# ===========================================================================
# ONTOLOGY SYSTEM PROMPT
# ===========================================================================

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a CV parser that outputs ONLY valid Turtle RDF.
    Do not output any explanation, prose, or markdown code fences.
    Start directly with the @prefix declarations, then the triples.

    Use these namespace prefixes exactly:
    @prefix cv:      <http://purl.org/captsolo/resume-rdf/0.2/cv#> .
    @prefix cvb:     <http://purl.org/captsolo/resume-rdf/0.2/base#> .
    @prefix cvx:     <http://example.org/cv-extension#> .
    @prefix foaf:    <http://xmlns.com/foaf/0.1/> .
    @prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
    @prefix dcterms: <http://purl.org/dc/terms/> .
    @prefix bibo:    <http://purl.org/ontology/bibo/> .
    @prefix :        <http://example.org/cv/> .

    PERSON
    :person a foaf:Person ;
        foaf:name "..." ;
        foaf:mbox <mailto:...> ;
        foaf:homepage <https://...> .

    :cv a cv:CV ;
        cv:aboutPerson :person ;
        cv:cvTitle "..." ;
        cv:lastUpdate "YYYY-MM-DD"^^xsd:date .

    WORK HISTORY
    Each position gets a cv:WorkHistory node linked from :cv via cv:hasWorkHistory.

    :wh_SLUG a cv:WorkHistory ;
        cv:employedIn :company_SLUG ;
        cv:jobTitle "..." ;
        cv:startDate "YYYY-MM-DD"^^xsd:date ;
        cv:endDate   "YYYY-MM-DD"^^xsd:date ;
        cv:jobDescription "..." .

    :company_SLUG a cv:Company ;
        cv:Name "..." ;
        cv:URL <https://...> ;
        cv:Industry "..." ;
        cv:Locality "..." ;
        cv:Country "..." .

    PROJECTS
    Each project/engagement is a cvx:Project node linked from its cv:WorkHistory
    via cvx:hasProject.

    :proj_SLUG a cvx:Project ;
        cvx:projectName         "..." ;
        cvx:projectDescription  "What the project was about." ;
        cvx:clientName          "..." ;
        cvx:roleTitle           "The person's role on this project." ;
        cvx:startDate           "YYYY-MM-DD"^^xsd:date ;
        cvx:endDate             "YYYY-MM-DD"^^xsd:date ;
        cvx:activitiesPerformed "What the person did, in detail." ;
        cvx:benefitsDelivered   "Outcomes and measurable impact." ;
        cvx:domain              "energy" ;
        cvx:usesSkill           :skill_SLUG .   # repeat for each skill used on this project

    Allowed domain values: energy, transportation, finance, healthcare, industry,
    telecom, public-sector, retail, technology, environment, other.
    Repeat cvx:domain triple for multiple sectors.

    For cvx:usesSkill, reference the IRI of an existing :skill_SLUG node defined in
    the SKILLS section. Only link skills that were explicitly applied on this project.
    Repeat the triple for each relevant skill.

    SKILLS
    :skill_SLUG a cv:Skill ;
        cv:skillName "..." ;
        cv:skillLevel "..." ;
        cv:skillYearsExperience "N"^^xsd:integer .
    Link from :cv via cv:hasSkill.

    FORMAL EDUCATION
    :edu_SLUG a cv:Education ;
        cv:degreeType   "..." ;
        cv:eduMajor     "..." ;
        cv:eduStartDate "YYYY-MM-DD"^^xsd:date ;
        cv:eduGradDate  "YYYY-MM-DD"^^xsd:date ;
        cv:studiedIn    :company_SLUG .
    Link from :cv via cv:hasEducation.

    MOOCs
    Online courses (Coursera, edX, LinkedIn Learning, Udemy, etc.).
    Each is a cvx:MOOC node linked from :cv via cvx:hasMOOC.

    :mooc_SLUG a cvx:MOOC ;
        cvx:courseTitle      "..." ;
        cvx:courseProvider   "Coursera / edX / Udemy / ..." ;
        cvx:issuingBody      "..." ;
        cvx:completionDate   "YYYY-MM-DD"^^xsd:date ;
        cvx:credentialURL    <https://...> ;
        cvx:courseTopics     "..." .
    Link from :cv via cvx:hasMOOC.

    AD-HOC TRAININGS
    Short courses, workshops, bootcamps, professional certifications.
    Each is a cvx:Training node linked from :cv via cvx:hasTraining.

    :training_SLUG a cvx:Training ;
        cvx:trainingTitle     "..." ;
        cvx:trainingProvider  "..." ;
        cvx:trainingDate      "YYYY-MM-DD"^^xsd:date ;
        cvx:trainingDuration  "..." ;
        cvx:certificationName "..." ;
        cvx:trainingTopics    "..." .
    Link from :cv via cvx:hasTraining.

    PERSONAL PROJECTS
    Side projects, open-source work, community initiatives, hardware projects, etc.
    Each is a cvx:PersonalProject node linked from :cv via cvx:hasPersonalProject.

    :pp_SLUG a cvx:PersonalProject ;
        cvx:projectName        "..." ;
        cvx:projectDescription "What the project is about." ;
        cvx:projectURL         <https://...> ;
        cvx:startDate          "YYYY-MM-DD"^^xsd:date ;
        cvx:endDate            "YYYY-MM-DD"^^xsd:date ;
        cvx:technologiesUsed   "..." ;
        cvx:domain             "technology" .
    Link from :cv via cvx:hasPersonalProject.

    PUBLICATIONS
    Academic papers, articles, reports, blog posts, patents, book chapters, etc.
    Use bibo: types. Each linked from :cv via cvx:hasPublication.

    bibo:AcademicArticle  peer-reviewed journal papers
    bibo:Article          magazine or blog articles
    bibo:Report           technical or institutional reports
    bibo:Patent           patents
    bibo:Book             books or book chapters

    :pub_SLUG a bibo:AcademicArticle ;
        dcterms:title            "..." ;
        dcterms:date             "YYYY-MM-DD"^^xsd:date ;
        bibo:doi                 "10.xxxx/..." ;
        bibo:uri                 <https://...> ;
        cvx:publicationVenue     "Journal / Conference / Publisher name" ;
        cvx:coAuthors            "Comma-separated co-author names" ;
        cvx:abstract             "Short abstract or description." .
    Link from :cv via cvx:hasPublication.

    SLUGS
    Build slugs from meaningful keywords:
      :wh_acme_2019, :proj_smartgrid_2022, :skill_python, :edu_msc_2010,
      :mooc_ml_coursera_2022, :training_iso42001_2024,
      :pp_ultrasound_oshw, :pub_ieee_ultrasound_2009

    Output ONLY raw Turtle. No prose before or after.
""")


# ===========================================================================
# HELPERS
# ===========================================================================

def read_pdf_as_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def build_user_content(file_path: str, extra_context: str) -> list:
    """Build the messages[0].content block for the Anthropic API call."""
    ext = os.path.splitext(file_path)[1].lower()
    suffix = (
        f"\n\nAdditional context from the CV owner: {extra_context}"
        if extra_context.strip()
        else ""
    )

    if ext == ".pdf":
        b64 = read_pdf_as_base64(file_path)
        return [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            },
            {
                "type": "text",
                "text": f"Parse this CV into Turtle RDF exactly as instructed.{suffix}",
            },
        ]
    else:
        text = read_text(file_path)
        return [
            {
                "type": "text",
                "text": (
                    f"Parse this CV into Turtle RDF exactly as instructed."
                    f"{suffix}\n\nCV content:\n\n{text}"
                ),
            }
        ]


def strip_fences(text: str) -> str:
    """Remove any markdown code fences Claude may have included."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def count_triples(ttl: str) -> int:
    """Rough triple count based on statement-ending punctuation."""
    return sum(
        1
        for line in ttl.splitlines()
        if line.strip()
        and not line.strip().startswith(("#", "@"))
        and (line.rstrip().endswith(".") or line.rstrip().endswith(";"))
    )


def extract_person_name(ttl: str) -> str | None:
    """Pull the foaf:name value out of the generated Turtle, if present."""
    m = re.search(r'foaf:name\s+"([^"]+)"', ttl)
    return m.group(1) if m else None


def validate_turtle(ttl: str) -> bool:
    """
    Parse the Turtle with rdflib to catch syntax errors.
    Returns True on success, False on failure.
    Requires: pip install rdflib
    """
    try:
        from rdflib import Graph
        g = Graph()
        g.parse(data=ttl, format="turtle")
        print(f"  v  rdflib: {len(g)} triples parsed successfully.")
        return True
    except ImportError:
        print("  .  rdflib not installed - skipping validation.")
        print("     Install with:  pip install rdflib")
        return True
    except Exception as exc:
        print(f"  x  rdflib validation error: {exc}", file=sys.stderr)
        return False


# ===========================================================================
# CORE API CALL
# ===========================================================================

def call_anthropic(
    file_path: str,
    extra_context: str,
    api_key: str,
    model: str,
    max_tokens: int,
    verbose: bool = True,
) -> tuple[str, dict]:
    """
    Call the Anthropic API using streaming and return (turtle_text, usage_dict).

    Streaming is required when max_tokens is large enough to risk exceeding
    the 10-minute non-streaming request window.
    """
    client = anthropic.Anthropic(api_key=api_key)
    content = build_user_content(file_path, extra_context)

    if verbose:
        print("Calling Anthropic API (streaming)...", end=" ", flush=True)

    raw_parts: list[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for chunk in stream.text_stream:
            raw_parts.append(chunk)
            if verbose:
                print(".", end="", flush=True)
        final = stream.get_final_message()

    if verbose:
        print(" done.")

    ttl = strip_fences("".join(raw_parts))
    usage = {
        "input_tokens":  final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
    }
    return ttl, usage


# ===========================================================================
# MAIN
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a CV into a Turtle RDF knowledge graph using the Anthropic API.\n"
            "Supports PDF, plain text (.txt), and Markdown (.md) input."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              python cv_to_knowledge_graph.py my_cv.pdf
              python cv_to_knowledge_graph.py my_cv.pdf --output graph.ttl
              python cv_to_knowledge_graph.py my_cv.pdf \\
                  --context "I work in energy and transport. Use English." \\
                  --validate
              python cv_to_knowledge_graph.py my_cv.pdf --model claude-opus-4-6
        """),
    )

    parser.add_argument(
        "cv_file",
        help="Path to the CV file (.pdf, .txt, or .md).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        metavar="FILE",
        help="Output Turtle file path (default: <cv_stem>.ttl).",
    )
    parser.add_argument(
        "--context", "-c",
        default="",
        metavar="TEXT",
        help=(
            "Extra context for the parser, e.g. preferred output language "
            "or main professional sectors."
        ),
    )
    parser.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help=(
            "Anthropic API key. "
            "Defaults to the ANTHROPIC_API_KEY environment variable. "
            "Get a key at: https://console.anthropic.com/settings/keys"
        ),
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        metavar="MODEL",
        help="Anthropic model to use (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=60000,
        metavar="N",
        help="Maximum output tokens (default: 60000).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the output Turtle with rdflib (requires: pip install rdflib).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output.",
    )

    args = parser.parse_args()
    verbose = not args.quiet

    # resolve output path
    out_path = args.output or (
        os.path.splitext(os.path.basename(args.cv_file))[0] + ".ttl"
    )

    # resolve API key
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "Error: no Anthropic API key found.\n"
            "  Set the ANTHROPIC_API_KEY environment variable, or use --api-key.\n"
            "  Get a key at: https://console.anthropic.com/settings/keys"
        )

    # check input file
    if not os.path.isfile(args.cv_file):
        sys.exit(f"Error: file not found: {args.cv_file}")

    ext = os.path.splitext(args.cv_file)[1].lower()
    if ext not in {".pdf", ".txt", ".md"}:
        sys.exit(f"Error: unsupported file type '{ext}'. Use .pdf, .txt, or .md.")

    # run
    if verbose:
        print(f"Input:   {args.cv_file}")
        print(f"Output:  {out_path}")
        print(f"Model:   {args.model}  (max_tokens={args.max_tokens})")

    ttl, usage = call_anthropic(
        file_path=args.cv_file,
        extra_context=args.context,
        api_key=api_key,
        model=args.model,
        max_tokens=args.max_tokens,
        verbose=verbose,
    )

    # optional validation
    if args.validate:
        if verbose:
            print("Validating Turtle...")
        validate_turtle(ttl)

    # write output
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ttl)
        f.write("\n")

    if verbose:
        n = count_triples(ttl)
        name = extract_person_name(ttl)
        print(f"Saved:   {out_path}  (~{n} triple statements)")
        if name:
            print(f"Person:  {name}")
        print(
            f"Tokens:  {usage['input_tokens']:,} in "
            f"/ {usage['output_tokens']:,} out"
        )


if __name__ == "__main__":
    main()