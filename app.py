"""
app.py  —  Streamlit web application
=====================================
Four-step pipeline: Upload → Consolidate → QA Chat → Export

Run:  streamlit run app.py

Secrets (.streamlit/secrets.toml):
    [app]
    password = "..."

    [anthropic]
    api_key = "sk-ant-..."
"""

import io
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

import resume_rdf
from resume_rdf import (
    audit_experience,
    consolidate_ttls,
    count_triples,
    extract_person_name,
    generate_graph_from_bytes,
    ttl_to_markdown,
    update_field,
    visualize_cv,
)


# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CV → Knowledge Graph",
    page_icon="🕸️",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { max-width: 840px; padding-top: 2rem; }
    .stCodeBlock   { font-size: 12px; }
    div[data-testid="stStatusWidget"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

def _check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title("🕸️ CV → Knowledge Graph")
    st.caption("Sign in to continue")
    st.divider()
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", use_container_width=True):
            if pwd == st.secrets["app"]["password"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# Session state helpers
# ══════════════════════════════════════════════════════════════════════════════

def _tmpdir() -> Path:
    if "tmpdir" not in st.session_state:
        st.session_state["tmpdir"] = tempfile.mkdtemp(prefix="resumeRDF_")
    return Path(st.session_state["tmpdir"])


def _step() -> int:
    return st.session_state.get("step", 1)


def _go(step: int) -> None:
    st.session_state["step"] = step


def _reset() -> None:
    for key in [
        "step", "ttl_files", "working_path", "working_name",
        "merge_stats", "chat_history", "pending_questions",
        "current_q", "exports",
    ]:
        st.session_state.pop(key, None)


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _docx_to_bytes(data: bytes) -> bytes | None:
    """Extract text from .docx and return as UTF-8 bytes, or None if unavailable."""
    try:
        import docx  # python-docx
        import io as _io
        doc = docx.Document(_io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text.encode("utf-8")
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Progress indicator
# ══════════════════════════════════════════════════════════════════════════════

_STEP_LABELS = ["1 · Upload", "2 · Consolidate", "3 · QA Chat", "4 · Export"]


def _render_progress() -> None:
    s = _step()
    cols = st.columns(len(_STEP_LABELS))
    for i, (col, label) in enumerate(zip(cols, _STEP_LABELS)):
        n = i + 1
        if n == s:
            colour, weight, border = "#3b5bdb", "700", "#3b5bdb"
        elif n < s:
            colour, weight, border = "#22c55e", "600", "#22c55e"
        else:
            colour, weight, border = "#94a3b8", "400", "#e2e8f0"
        col.markdown(
            f'<div style="text-align:center;font-size:13px;font-weight:{weight};'
            f'color:{colour};border-bottom:3px solid {border};padding-bottom:4px">'
            f"{label}</div>",
            unsafe_allow_html=True,
        )
    st.write("")


# ══════════════════════════════════════════════════════════════════════════════
# Step 1 — Upload & Parse
# ══════════════════════════════════════════════════════════════════════════════

def step1() -> None:
    st.subheader("1 · Upload CVs")
    st.caption(
        "Upload one or more CV files. "
        "`.ttl` files are used as-is; others are parsed via Claude."
    )

    uploaded = st.file_uploader(
        "Drop CV files here",
        type=["pdf", "txt", "md", "ttl", "docx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    extra_context = st.text_area(
        "Extra context (optional)",
        placeholder="E.g. 'Energy sector, English labels.'",
        height=68,
    )

    if uploaded and st.button("Parse CVs →", type="primary", use_container_width=True):
        api_key = st.secrets["anthropic"]["api_key"]
        tmpdir = _tmpdir()
        ttl_files: list[tuple[str, str]] = []

        bar = st.progress(0.0, text="Processing files…")
        for i, f in enumerate(uploaded):
            stem = Path(f.name).stem
            data = f.read()
            ext = Path(f.name).suffix.lower()
            bar.progress((i + 0.5) / len(uploaded), text=f"Processing {f.name}…")

            if ext == ".ttl":
                out = tmpdir / f"{stem}.ttl"
                out.write_bytes(data)
                ttl_files.append((stem, str(out)))
                bar.progress((i + 1) / len(uploaded))
                continue

            if ext == ".docx":
                converted = _docx_to_bytes(data)
                if converted is None:
                    st.warning(f"python-docx not installed — skipping {f.name}")
                    continue
                data, f_name = converted, f"{stem}.txt"
            else:
                f_name = f.name

            with st.status(f"Parsing {f.name}…", expanded=False):
                try:
                    turtle, usage = generate_graph_from_bytes(
                        file_bytes=data,
                        file_name=f_name,
                        api_key=api_key,
                        extra_context=extra_context,
                    )
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    bar.progress((i + 1) / len(uploaded))
                    continue
                n = count_triples(turtle)
                st.write(f"✅ {n} triples · {usage['output_tokens']:,} tokens out")

            out = tmpdir / f"{stem}.ttl"
            out.write_text(turtle, encoding="utf-8")
            ttl_files.append((stem, str(out)))
            bar.progress((i + 1) / len(uploaded))

        bar.empty()

        if not ttl_files:
            st.error("No CVs were successfully parsed.")
            return

        st.session_state["ttl_files"] = ttl_files

    # ── results (shown whenever ttl_files is set) ──────────────────────────────
    ttl_files = st.session_state.get("ttl_files")
    if not ttl_files:
        return

    st.divider()
    st.caption(f"**{len(ttl_files)} TTL file(s) ready:**")
    for name, path_str in ttl_files:
        n = count_triples(Path(path_str).read_text(encoding="utf-8"))
        st.markdown(f"- `{name}.ttl` — {n} triples")

    zip_data = _make_zip(
        {f"{name}.ttl": Path(p).read_bytes() for name, p in ttl_files}
    )

    col1, col2 = st.columns(2)
    col1.download_button(
        "⬇️ Download all TTLs (.zip)",
        data=zip_data,
        file_name="cvs.zip",
        mime="application/zip",
        use_container_width=True,
    )

    n_ttl = len(ttl_files)
    target = 2 if n_ttl > 1 else 3
    label = "Proceed to consolidation →" if n_ttl > 1 else "Proceed to QA Chat →"

    if col2.button(label, type="primary", use_container_width=True):
        if target == 3:
            name, path_str = ttl_files[0]
            st.session_state["working_path"] = path_str
            st.session_state["working_name"] = name
        _go(target)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Step 2 — Consolidation
# ══════════════════════════════════════════════════════════════════════════════

def step2() -> None:
    ttl_files: list[tuple[str, str]] = st.session_state.get("ttl_files", [])

    st.subheader("2 · Consolidation")
    st.caption(f"Merge {len(ttl_files)} TTL files into one enriched, deduplicated graph.")

    for name, path_str in ttl_files:
        n = count_triples(Path(path_str).read_text(encoding="utf-8"))
        st.markdown(f"- `{name}.ttl` — {n} triples")

    strategy = st.radio(
        "Merge strategy",
        options=["longest", "concat", "llm"],
        captions=[
            "Keep the longest description (no API calls)",
            "Concatenate all descriptions with ' | ' (no API calls)",
            "Ask Claude to synthesise one coherent text (cached)",
        ],
        horizontal=True,
    )

    if st.button("Merge CVs →", type="primary", use_container_width=True):
        tmpdir = _tmpdir()
        api_key = st.secrets["anthropic"]["api_key"]
        out_path = tmpdir / "merged.ttl"
        paths = [Path(p) for _, p in ttl_files]

        with st.spinner("Merging…"):
            try:
                stats = consolidate_ttls(
                    paths,
                    out_path,
                    strategy=strategy,
                    api_key=api_key if strategy == "llm" else None,
                )
            except Exception as exc:
                st.error(f"Merge failed: {exc}")
                return

        st.session_state["merge_stats"] = stats
        st.session_state["merge_strategy"] = strategy
        st.session_state["working_path"] = str(out_path)
        st.session_state["working_name"] = "merged"

    # ── results ────────────────────────────────────────────────────────────────
    if "merge_stats" not in st.session_state:
        return

    stats = st.session_state["merge_stats"]
    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("Input triples", stats.input_triples)
    col2.metric("Conflicts resolved", stats.conflicts_resolved)
    col3.metric("Output triples", stats.output_triples)

    if st.session_state.get("merge_strategy") == "llm":
        st.caption(
            f"LLM API calls: **{stats.llm_calls}** · "
            f"Cache hits: **{stats.llm_cache_hits}**"
        )

    out_path = Path(st.session_state["working_path"])
    col_dl, col_next = st.columns(2)

    col_dl.download_button(
        "⬇️ Download merged TTL",
        data=out_path.read_bytes(),
        file_name="merged.ttl",
        mime="text/turtle",
        use_container_width=True,
    )

    if col_next.button("Proceed to QA Chat →", type="primary", use_container_width=True):
        _go(3)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Step 3 — QA Chat
# ══════════════════════════════════════════════════════════════════════════════

def step3() -> None:
    working_path = Path(st.session_state.get("working_path", ""))
    working_name = st.session_state.get("working_name", "cv")

    st.subheader("3 · QA Chat")

    if not working_path.exists():
        st.error("Working TTL not found — please restart from Step 1.")
        if st.button("← Back to Step 1"):
            _reset()
            st.rerun()
        return

    # ── initialise on first visit ──────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        questions = audit_experience(working_path)
        st.session_state["pending_questions"] = questions
        st.session_state["current_q"] = 0
        st.session_state["chat_history"] = []

        if questions:
            q = questions[0]
            intro = (
                f"I found **{len(questions)} field(s)** that need filling in "
                f"`{working_name}.ttl`. Let's go through them one by one.\n\n"
                f"**[{q.slug}] {q.field}**\n\n{q.question}"
            )
        else:
            intro = "✅ No missing fields — the graph is complete. Click **Proceed to export** whenever you're ready."

        st.session_state["chat_history"].append({"role": "assistant", "content": intro})

    # ── proceed button at the top ──────────────────────────────────────────────
    if st.button("Proceed to export →", type="primary", use_container_width=True):
        _go(4)
        st.rerun()

    st.divider()

    # ── render chat history ────────────────────────────────────────────────────
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── chat input ─────────────────────────────────────────────────────────────
    user_input = st.chat_input("Type your answer, or 'done' to skip remaining…")
    if not user_input:
        return

    st.session_state["chat_history"].append({"role": "user", "content": user_input})

    if user_input.strip().lower() in {"done", "skip", "exit", "quit"}:
        reply = "Skipping remaining questions. Click **Proceed to export** when ready."
        st.session_state["pending_questions"] = []
    else:
        questions: list = st.session_state.get("pending_questions", [])
        q_idx: int = st.session_state.get("current_q", 0)

        if questions and 0 <= q_idx < len(questions):
            q = questions[q_idx]
            try:
                update_field(working_path, q.slug, q.field, user_input.strip())
                reply = f"✅ Set **{q.field}** = `{user_input.strip()}`"
                next_idx = q_idx + 1
                if next_idx < len(questions):
                    nq = questions[next_idx]
                    reply += f"\n\n**[{nq.slug}] {nq.field}**\n\n{nq.question}"
                    st.session_state["current_q"] = next_idx
                else:
                    reply += "\n\n✅ All questions answered! Click **Proceed to export** when ready."
                    st.session_state["pending_questions"] = []
            except Exception as exc:
                reply = f"⚠️ Could not update field: {exc}"
                st.session_state["current_q"] = q_idx + 1
        else:
            reply = "No more questions. Click **Proceed to export** when ready."

    st.session_state["chat_history"].append({"role": "assistant", "content": reply})
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Step 4 — Export
# ══════════════════════════════════════════════════════════════════════════════

def step4() -> None:
    working_path = Path(st.session_state.get("working_path", ""))
    working_name = st.session_state.get("working_name", "cv")

    st.subheader("4 · Export")

    if not working_path.exists():
        st.error("Working TTL not found — please restart from Step 1.")
        if st.button("← Back to Step 1"):
            _reset()
            st.rerun()
        return

    if "exports" not in st.session_state:
        tmpdir = _tmpdir()
        with st.spinner("Generating exports…"):
            md = ttl_to_markdown(working_path)
            html_path = tmpdir / f"{working_name}_graph.html"
            visualize_cv(working_path, html_path)
            html_bytes = html_path.read_bytes()
            ttl_bytes = working_path.read_bytes()
            zip_bytes = _make_zip({
                f"{working_name}.ttl":          ttl_bytes,
                f"{working_name}.md":           md.encode("utf-8"),
                f"{working_name}_graph.html":   html_bytes,
            })
            name = extract_person_name(working_path.read_text(encoding="utf-8")) or working_name

        st.session_state["exports"] = {
            "ttl_bytes":  ttl_bytes,
            "md":         md,
            "html_bytes": html_bytes,
            "zip_bytes":  zip_bytes,
            "name":       name,
        }

    exports = st.session_state["exports"]
    name = exports["name"]
    n = count_triples(exports["ttl_bytes"].decode("utf-8"))

    st.success(f"✅ **{name}** — {n} triples")

    col1, col2, col3, col4 = st.columns(4)
    col1.download_button(
        "⬇️ TTL",
        data=exports["ttl_bytes"],
        file_name=f"{working_name}.ttl",
        mime="text/turtle",
        use_container_width=True,
    )
    col2.download_button(
        "⬇️ Markdown",
        data=exports["md"].encode("utf-8"),
        file_name=f"{working_name}.md",
        mime="text/markdown",
        use_container_width=True,
    )
    col3.download_button(
        "⬇️ Graph HTML",
        data=exports["html_bytes"],
        file_name=f"{working_name}_graph.html",
        mime="text/html",
        use_container_width=True,
    )
    col4.download_button(
        "⬇️ ZIP (all)",
        data=exports["zip_bytes"],
        file_name=f"{working_name}_cv_package.zip",
        mime="application/zip",
        use_container_width=True,
    )

    with st.expander("Preview Markdown CV", expanded=True):
        st.markdown(exports["md"])

    with st.expander("Preview Turtle RDF", expanded=False):
        st.code(exports["ttl_bytes"].decode("utf-8"), language="turtle")

    st.divider()
    if st.button("🔄 Start over", use_container_width=True):
        _reset()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

st.title("🕸️ CV → Knowledge Graph")
st.caption(
    f"Parse, consolidate, audit, and export CVs as Turtle RDF knowledge graphs.  "
    f"v{resume_rdf.__version__}"
)
st.divider()

_render_progress()

s = _step()
if s == 1:
    step1()
elif s == 2:
    step2()
elif s == 3:
    step3()
elif s == 4:
    step4()
