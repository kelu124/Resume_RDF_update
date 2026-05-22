"""
app.py  —  Streamlit web application
=====================================
Thin wrapper around the ``resume_rdf`` library.  All parsing, caching, and
API logic lives in the package; this file handles the Streamlit UI only.

Run:  streamlit run app.py
"""

import streamlit as st

import resume_rdf

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
# 2.  UI
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

    with st.status("Calling Claude…", expanded=True) as status:
        st.write("📤 Sending CV to Anthropic API…")
        try:
            turtle, usage = resume_rdf.generate_graph_from_bytes(
                file_bytes=file_bytes,
                file_name=file_name,
                api_key=st.secrets["anthropic"]["api_key"],
                extra_context=extra_context,
            )
        except Exception as exc:
            status.update(label="API error", state="error")
            st.error(f"Anthropic API call failed: {exc}")
            st.stop()

        n_triples = resume_rdf.count_triples(turtle)
        st.write(f"✅ Graph generated — ~{n_triples} triple statements")
        st.write(
            f"📊 Tokens used: {usage['input_tokens']:,} in / "
            f"{usage['output_tokens']:,} out"
        )

        status.update(label="Done!", state="complete", expanded=False)

    st.session_state["ttl"]       = turtle
    st.session_state["ttl_name"]  = ttl_name
    st.session_state["n_triples"] = n_triples

# ── results panel ────────────────────────────────────────────────────────────
if "ttl" in st.session_state:
    turtle    = st.session_state["ttl"]
    ttl_name  = st.session_state["ttl_name"]
    n_triples = st.session_state["n_triples"]

    st.divider()
    st.subheader("4 · Result")

    col1, col2, col3 = st.columns(3)
    col1.metric("Triple statements", f"~{n_triples}")
    col2.metric("Namespaces", len(resume_rdf.NAMESPACES))
    col3.metric("Format", "Turtle RDF")

    st.download_button(
        label="⬇️ Download .ttl",
        data=turtle.encode("utf-8"),
        file_name=ttl_name,
        mime="text/turtle",
        use_container_width=True,
    )

    with st.expander("View Turtle RDF", expanded=False):
        st.code(turtle, language="turtle")

    st.caption(
        "Load the .ttl file into GraphDB, Apache Jena Fuseki, Stardog, "
        "or Oxigraph to query it with SPARQL."
    )
