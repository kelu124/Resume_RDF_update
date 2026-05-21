"""
CV → RDF Knowledge Graph  ·  Streamlit app
==========================================
Run:  streamlit run app.py
"""

import base64
import textwrap

import anthropic
import streamlit as st

# ── page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CV → Knowledge Graph",
    page_icon="🕸️",
    layout="centered",
)

# ── minimal custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { max-width: 780px; padding-top: 2rem; }
    .stCodeBlock { font-size: 12px; }
    div[data-testid="stStatusWidget"] { display: none; }
    .step-badge {
        display: inline-block;
        background: #f0f4ff;
        color: #3b5bdb;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# 1.  PASSWORD GATE
# ═══════════════════════════════════════════════════════════════════════════

def check_password() -> bool:
    """Return True once the correct password has been entered."""
    if st.session_state.get("authenticated"):
        return True

    st.title("🕸️ CV → Knowledge Graph")
    st.caption("Sign in to continue")
    st.divider()

    with st.form("login_form"):
        pwd = st.text_input("Password", type="password", placeholder="Enter app password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        if pwd == st.secrets["app"]["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


if not check_password():
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 2.  ONTOLOGY SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = textwrap.dedent("""    You are a CV parser that outputs ONLY valid Turtle RDF.
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

    ── PERSON ──────────────────────────────────────────────────────────────────────
    :person a foaf:Person ;
        foaf:name "..." ;
        foaf:mbox <mailto:...> ;       # if available
        foaf:homepage <https://...> .  # if available

    :cv a cv:CV ;
        cv:aboutPerson :person ;
        cv:cvTitle "..." ;
        cv:lastUpdate "YYYY-MM-DD"^^xsd:date .

    ── WORK HISTORY ──────────────────────────────────────────────────────────────────────
    Each position gets a cv:WorkHistory node linked from :cv via cv:hasWorkHistory.

    :wh_SLUG a cv:WorkHistory ;
        cv:employedIn :company_SLUG ;
        cv:jobTitle "..." ;
        cv:startDate "YYYY-MM-DD"^^xsd:date ;
        cv:endDate   "YYYY-MM-DD"^^xsd:date ;  # omit if current
        cv:jobDescription "..." .

    :company_SLUG a cv:Company ;
        cv:Name "..." ;
        cv:URL <https://...> ;     # if available
        cv:Industry "..." ;
        cv:Locality "..." ;
        cv:Country "..." .

    ── PROJECTS ──────────────────────────────────────────────────────────────────────
    Each project/engagement is a cvx:Project node linked from its cv:WorkHistory
    via cvx:hasProject.

    :proj_SLUG a cvx:Project ;
        cvx:projectName         "..." ;
        cvx:projectDescription  "What the project was about." ;
        cvx:clientName          "..." ;
        cvx:roleTitle           "The person's role on this project." ;
        cvx:startDate           "YYYY-MM-DD"^^xsd:date ;
        cvx:endDate             "YYYY-MM-DD"^^xsd:date ;  # omit if ongoing
        cvx:activitiesPerformed "What the person did, in detail." ;
        cvx:benefitsDelivered   "Outcomes and measurable impact." ;
        cvx:domain              "energy" .  # repeat triple for multiple sectors

    Allowed domain values: energy, transportation, finance, healthcare, industry,
    telecom, public-sector, retail, technology, environment, other.

    ── SKILLS ──────────────────────────────────────────────────────────────────────
    :skill_SLUG a cv:Skill ;
        cv:skillName "..." ;
        cv:skillLevel "..." ;
        cv:skillYearsExperience "N"^^xsd:integer .

    Link from :cv via cv:hasSkill.

    ── FORMAL EDUCATION ──────────────────────────────────────────────────────────────────────
    :edu_SLUG a cv:Education ;
        cv:degreeType   "..." ;
        cv:eduMajor     "..." ;
        cv:eduStartDate "YYYY-MM-DD"^^xsd:date ;
        cv:eduGradDate  "YYYY-MM-DD"^^xsd:date ;
        cv:studiedIn    :company_SLUG .

    Link from :cv via cv:hasEducation.

    ── MOOCs ──────────────────────────────────────────────────────────────────────
    Online courses (Coursera, edX, LinkedIn Learning, Udemy, etc.).
    Each is a cvx:MOOC node linked from :cv via cvx:hasMOOC.

    :mooc_SLUG a cvx:MOOC ;
        cvx:courseTitle      "..." ;
        cvx:courseProvider   "Coursera / edX / Udemy / ..." ;
        cvx:issuingBody      "..." ;           # university or organisation behind the course
        cvx:completionDate   "YYYY-MM-DD"^^xsd:date ;
        cvx:credentialURL    <https://...> ;   # certificate link if available
        cvx:courseTopics     "..." .           # brief description of subjects covered

    Link from :cv via cvx:hasMOOC.

    ── AD-HOC TRAININGS ──────────────────────────────────────────────────────────────────────
    Short courses, workshops, bootcamps, professional certifications (not full degrees or MOOCs).
    Each is a cvx:Training node linked from :cv via cvx:hasTraining.

    :training_SLUG a cvx:Training ;
        cvx:trainingTitle     "..." ;
        cvx:trainingProvider  "..." ;          # organisation that delivered the training
        cvx:trainingDate      "YYYY-MM-DD"^^xsd:date ;
        cvx:trainingDuration  "..." ;          # e.g. "2 days", "40 hours" if mentioned
        cvx:certificationName "..." ;          # official cert name if one was awarded; omit otherwise
        cvx:trainingTopics    "..." .          # subjects covered

    Link from :cv via cvx:hasTraining.

    ── PERSONAL PROJECTS ──────────────────────────────────────────────────────────────────────
    Side projects, open-source work, community initiatives, hardware projects, etc.
    Each is a cvx:PersonalProject node linked from :cv via cvx:hasPersonalProject.

    :pp_SLUG a cvx:PersonalProject ;
        cvx:projectName        "..." ;
        cvx:projectDescription "What the project is about." ;
        cvx:projectURL         <https://...> ;   # repo, website, etc. if available
        cvx:startDate          "YYYY-MM-DD"^^xsd:date ;
        cvx:endDate            "YYYY-MM-DD"^^xsd:date ;  # omit if ongoing
        cvx:technologiesUsed   "..." ;           # tools, languages, frameworks
        cvx:domain             "technology" .    # same allowed values as cvx:Project

    Link from :cv via cvx:hasPersonalProject.

    ── PUBLICATIONS ──────────────────────────────────────────────────────────────────────
    Academic papers, articles, reports, blog posts, patents, book chapters, etc.
    Use bibo: (Bibliographic Ontology) types. Each is linked from :cv via cvx:hasPublication.

    bibo:AcademicArticle  for peer-reviewed journal papers
    bibo:Article          for magazine or blog articles
    bibo:Report           for technical or institutional reports
    bibo:Patent           for patents
    bibo:Book             for books or book chapters

    :pub_SLUG a bibo:AcademicArticle ;   # or other bibo type as appropriate
        dcterms:title            "..." ;
        dcterms:date             "YYYY-MM-DD"^^xsd:date ;
        bibo:doi                 "10.xxxx/..." ;   # omit if not available
        bibo:uri                 <https://...> ;   # URL if available
        cvx:publicationVenue     "Journal / Conference / Publisher name" ;
        cvx:coAuthors            "Comma-separated co-author names" ;
        cvx:abstract             "Short abstract or description." .

    Link from :cv via cvx:hasPublication.

    ── SLUGS ──────────────────────────────────────────────────────────────────────
    Build slugs from meaningful keywords:
      :wh_acme_2019, :proj_smartgrid_2022, :skill_python, :edu_msc_2010,
      :mooc_ml_coursera_2022, :training_iso42001_2024,
      :pp_ultrasound_oshw, :pub_ieee_ultrasound_2009

    Output ONLY raw Turtle. No prose before or after.
""")


# ═══════════════════════════════════════════════════════════════════════════
# 3.  CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def build_user_content(file_bytes: bytes, file_name: str, extra_context: str) -> list:
    """Build the content block for the Anthropic API call."""
    suffix = (
        f"\n\nAdditional context from the CV owner: {extra_context}"
        if extra_context.strip()
        else ""
    )
    ext = file_name.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
        return [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            },
            {
                "type": "text",
                "text": f"Parse this CV into Turtle RDF exactly as instructed.{suffix}",
            },
        ]
    else:
        text = file_bytes.decode("utf-8", errors="replace")
        return [
            {
                "type": "text",
                "text": (
                    f"Parse this CV into Turtle RDF exactly as instructed."
                    f"{suffix}\n\nCV content:\n\n{text}"
                ),
            }
        ]


def call_anthropic(file_bytes: bytes, file_name: str, extra_context: str) -> tuple[str, dict]:
    """Call the Anthropic API using streaming (required for large max_tokens)."""
    client = anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])
    user_content = build_user_content(file_bytes, file_name, extra_context)

    raw_parts = []
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=60000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        for chunk in stream.text_stream:
            raw_parts.append(chunk)
        final = stream.get_final_message()

    raw = "".join(raw_parts)
    # strip any accidental markdown fences
    lines = raw.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    ttl = "\n".join(lines).strip()

    usage = {
        "input_tokens": final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
    }
    return ttl, usage


def count_triples(ttl: str) -> int:
    return sum(
        1 for line in ttl.splitlines()
        if line.strip()
        and not line.strip().startswith(("#", "@"))
        and (line.rstrip().endswith(".") or line.rstrip().endswith(";"))
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4.  UI
# ═══════════════════════════════════════════════════════════════════════════

st.title("🕸️ CV → Knowledge Graph")
st.caption(
    "Parses a CV into a Turtle RDF knowledge graph using the "
    "[ResumeRDF](http://rdfs.org/resume-rdf/) ontology + a custom project extension."
)
st.divider()

# ── upload ───────────────────────────────────────────────────────────────────
st.subheader("1 · Upload CV")
uploaded = st.file_uploader(
    "Drop your CV here",
    type=["pdf", "txt", "md"],
    label_visibility="collapsed",
)

# ── context ──────────────────────────────────────────────────────────────────
st.subheader("2 · Additional context  *(optional)*")
extra_context = st.text_area(
    "Extra context",
    placeholder=(
        "E.g. 'My name is Jean Dupont. I work mainly in the energy and "
        "transport sectors. Output English labels.'"
    ),
    height=90,
    label_visibility="collapsed",
)

# ── run ───────────────────────────────────────────────────────────────────────
st.subheader("3 · Generate")
run = st.button(
    "Generate knowledge graph →",
    disabled=uploaded is None,
    use_container_width=True,
    type="primary",
)

if run and uploaded:
    file_bytes = uploaded.read()
    file_name  = uploaded.name
    stem       = file_name.rsplit(".", 1)[0]
    ttl_name   = f"{stem}.ttl"

    # ── step 1: call API ─────────────────────────────────────────────────
    with st.status("Calling Claude…", expanded=True) as status:
        st.write("📤 Sending CV to Anthropic API…")
        try:
            ttl, usage = call_anthropic(file_bytes, file_name, extra_context)
        except Exception as exc:
            status.update(label="API error", state="error")
            st.error(f"Anthropic API call failed: {exc}")
            st.stop()

        n_triples = count_triples(ttl)
        st.write(f"✅ Graph generated — ~{n_triples} triple statements")
        st.write(
            f"📊 Tokens used: {usage['input_tokens']:,} in / "
            f"{usage['output_tokens']:,} out"
        )

        status.update(label="Done!", state="complete", expanded=False)

    # ── store in session so we can show results after status closes ──────
    st.session_state["ttl"]      = ttl
    st.session_state["ttl_name"] = ttl_name
    st.session_state["n_triples"] = n_triples

# ── results panel ────────────────────────────────────────────────────────────
if "ttl" in st.session_state:
    ttl      = st.session_state["ttl"]
    ttl_name = st.session_state["ttl_name"]
    n_triples = st.session_state["n_triples"]

    st.divider()
    st.subheader("4 · Result")

    col1, col2, col3 = st.columns(3)
    col1.metric("Triple statements", f"~{n_triples}")
    col2.metric("Namespaces", 8)
    col3.metric("Format", "Turtle RDF")

    st.download_button(
        label="⬇️ Download .ttl",
        data=ttl.encode("utf-8"),
        file_name=ttl_name,
        mime="text/turtle",
        use_container_width=True,
    )

    with st.expander("View Turtle RDF", expanded=False):
        st.code(ttl, language="turtle")

    st.caption(
        "Load the .ttl file into GraphDB, Apache Jena Fuseki, Stardog, "
        "or Oxigraph to query it with SPARQL."
    )