"""
app/streamlit_app.py — AI Research KG Explorer
"""

import base64, os, tempfile
import streamlit as st
from SPARQLWrapper import SPARQLWrapper, JSON
from pyvis.network import Network

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FUSEKI_ENDPOINT = os.environ.get("FUSEKI_ENDPOINT", "http://localhost:3030/papers/sparql")
FUSEKI_USER     = os.environ.get("FUSEKI_USER", "admin")
FUSEKI_PASS     = os.environ.get("FUSEKI_PASS", "admin")

TOPIC_COLORS = {
    "Language Models":        "#4e79a7",
    "Computer Vision":        "#f28e2b",
    "Generative Models":      "#e15759",
    "Reinforcement Learning": "#76b7b2",
    "Optimization & Training":"#59a14f",
    "AI Safety & Ethics":     "#edc948",
}
DEFAULT_TOPIC_COLOR = "#b07aa1"

st.set_page_config(
    page_title="AI Research KG Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal global CSS
st.markdown("""
<style>
  /* tighter section headers */
  h3 { margin-top: 0.6rem !important; margin-bottom: 0.3rem !important; }
  /* card box */
  .paper-card {
    background: #1e2130;
    border: 1px solid #2e3250;
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    margin-bottom: 0.5rem;
  }
  .paper-title { font-size: 1rem; font-weight: 700; line-height: 1.4; margin-bottom: 0.5rem; }
  .meta-row { font-size: 0.82rem; color: #9ca3af; margin: 0.15rem 0; }
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
  }
  /* similar paper row */
  .sim-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid #2e3250;
  }
  .sim-title { flex: 1; font-size: 0.85rem; }
  .sim-score { font-size: 0.78rem; color: #9ca3af; min-width: 2.5rem; text-align: right; }
  .sim-bar-bg { flex: 0 0 80px; background:#2e3250; border-radius:4px; height:6px; }
  .sim-bar-fill { height:6px; border-radius:4px; background:#3b82f6; }
  /* entity chips */
  .chip-per {
    display:inline-block; margin:2px 3px;
    background:#3b1a1a; color:#fca5a5;
    border:1px solid #7f1d1d;
    padding:2px 8px; border-radius:6px; font-size:0.78rem;
  }
  .chip-org {
    display:inline-block; margin:2px 3px;
    background:#1a2540; color:#93c5fd;
    border:1px solid #1e3a5f;
    padding:2px 8px; border-radius:6px; font-size:0.78rem;
  }
  /* section divider */
  .section-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #6b7280;
    margin: 1rem 0 0.4rem;
  }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------
@st.cache_resource
def get_sparql() -> SPARQLWrapper:
    s = SPARQLWrapper(FUSEKI_ENDPOINT)
    s.setCredentials(FUSEKI_USER, FUSEKI_PASS)
    s.setReturnFormat(JSON)
    return s

def run_query(query: str) -> list[dict]:
    sparql = get_sparql()
    sparql.setQuery(query)
    try:
        return sparql.query().convert()["results"]["bindings"]
    except Exception as e:
        st.error(f"SPARQL error: {e}")
        return []

def val(b: dict, k: str, default: str = "") -> str:
    return b.get(k, {}).get("value", default)

def check_connection() -> bool:
    try:
        rows = run_query("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o } LIMIT 1")
        return bool(rows)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_topics() -> list[str]:
    rows = run_query("""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT DISTINCT ?label WHERE {
            ?t a skos:Concept ; skos:prefLabel ?label .
        } ORDER BY ?label
    """)
    return [val(r, "label") for r in rows]

@st.cache_data(ttl=300)
def fetch_papers(topic_filter: str = "All") -> list[dict]:
    clause = ""
    if topic_filter != "All":
        clause = f"""
            ?paper <http://example.org/aikg/belongsToTopic> ?t .
            ?t <http://www.w3.org/2004/02/skos/core#prefLabel> "{topic_filter}" .
        """
    rows = run_query(f"""
        PREFIX dc:   <http://purl.org/dc/elements/1.1/>
        PREFIX ex:   <http://example.org/aikg/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?paper ?id ?title ?topic ?year ?venue ?citations WHERE {{
            ?paper a ex:Paper ; dc:identifier ?id ; dc:title ?title .
            {clause}
            OPTIONAL {{ ?paper ex:belongsToTopic ?t . ?t skos:prefLabel ?topic . }}
            OPTIONAL {{ ?paper dc:date     ?year . }}
            OPTIONAL {{ ?paper ex:venue    ?venue . }}
            OPTIONAL {{ ?paper ex:citationCount ?citations . }}
        }} ORDER BY ?title
    """)
    seen, out = set(), []
    for r in rows:
        pid = val(r, "id")
        if pid not in seen:
            seen.add(pid)
            out.append({
                "uri": val(r, "paper"), "id": pid,
                "title": val(r, "title"), "topic": val(r, "topic"),
                "year": val(r, "year")[:4] if val(r, "year") else "",
                "venue": val(r, "venue"), "citations": val(r, "citations"),
            })
    return out

@st.cache_data(ttl=300)
def fetch_authors(paper_uri: str) -> list[str]:
    rows = run_query(f"""
        PREFIX dc: <http://purl.org/dc/elements/1.1/>
        SELECT ?author WHERE {{ <{paper_uri}> dc:creator ?author . }}
    """)
    return [val(r, "author") for r in rows]

@st.cache_data(ttl=300)
def fetch_similar(paper_uri: str) -> list[dict]:
    rows = run_query(f"""
        PREFIX ex: <http://example.org/aikg/>
        PREFIX dc: <http://purl.org/dc/elements/1.1/>
        SELECT ?other ?title ?score WHERE {{
            {{
                ?sim ex:paper1 <{paper_uri}> ; ex:paper2 ?other ; ex:similarityScore ?score .
            }} UNION {{
                ?sim ex:paper2 <{paper_uri}> ; ex:paper1 ?other ; ex:similarityScore ?score .
            }}
            ?other dc:title ?title .
            FILTER(?score >= 0.35)
        }} ORDER BY DESC(?score) LIMIT 10
    """)
    return [{"uri": val(r,"other"), "title": val(r,"title"),
             "score": float(val(r,"score","0"))} for r in rows]

@st.cache_data(ttl=300)
def fetch_entities(paper_uri: str) -> list[dict]:
    rows = run_query(f"""
        PREFIX ex:   <http://example.org/aikg/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX org:  <http://www.w3.org/ns/org#>
        PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?name ?type ?country WHERE {{
            <{paper_uri}> ex:acknowledges ?e .
            ?e foaf:name ?name ; rdf:type ?type .
            OPTIONAL {{ ?e ex:country ?country . }}
        }}
    """)
    out = []
    for r in rows:
        t = val(r, "type")
        out.append({
            "name":    val(r, "name"),
            "type":    "ORG" if "Organization" in t else "PER",
            "country": val(r, "country"),
        })
    return out

@st.cache_data(ttl=300)
def fetch_graph_data(sim_threshold: float, show_persons: bool) -> dict:
    papers = run_query("""
        PREFIX dc:   <http://purl.org/dc/elements/1.1/>
        PREFIX ex:   <http://example.org/aikg/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?paper ?id ?title ?topic WHERE {
            ?paper a ex:Paper ; dc:identifier ?id ; dc:title ?title .
            OPTIONAL { ?paper ex:belongsToTopic ?t . ?t skos:prefLabel ?topic . }
        }
    """)
    sims = run_query(f"""
        PREFIX ex: <http://example.org/aikg/>
        SELECT ?p1 ?p2 ?score WHERE {{
            ?sim a ex:SimilarityStatement ;
                 ex:paper1 ?p1 ; ex:paper2 ?p2 ; ex:similarityScore ?score .
            FILTER(?score >= {sim_threshold})
        }}
    """)
    orgs = run_query("""
        PREFIX ex:   <http://example.org/aikg/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX org:  <http://www.w3.org/ns/org#>
        SELECT ?paper ?name WHERE {
            ?paper ex:acknowledges ?e .
            ?e a org:Organization ; foaf:name ?name .
        }
    """)
    persons = []
    if show_persons:
        persons = run_query("""
            PREFIX ex:   <http://example.org/aikg/>
            PREFIX foaf: <http://xmlns.com/foaf/0.1/>
            SELECT ?paper ?name WHERE {
                ?paper ex:acknowledges ?e .
                ?e a foaf:Person ; foaf:name ?name .
            }
        """)
    return {"papers": papers, "sims": sims, "orgs": orgs, "persons": persons}

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## AI Research KG Explorer")
    st.divider()
    page = st.radio("Navigate", ["📄 Research Radar", "🕸️ Landscape Explorer"],
                    label_visibility="collapsed")
    st.divider()

    connected = check_connection()
    st.markdown(
        f"{'🟢' if connected else '🔴'} "
        f"{'Fuseki connected' if connected else 'Fuseki unreachable'}"
    )
    st.divider()

    if page == "📄 Research Radar":
        topics = ["All"] + fetch_topics()
        topic_filter = st.selectbox("Filter by topic", topics)
    else:
        st.markdown("**Graph filters**")
        show_papers  = st.checkbox("Papers",        value=True)
        show_topics  = st.checkbox("Topics",        value=True)
        show_orgs    = st.checkbox("Organizations", value=True)
        show_persons = st.checkbox("Persons",       value=False)
        sim_threshold = st.slider(
            "Similarity threshold", 0.35, 1.0, 0.6, 0.05,
            format="%.2f",
        )

# ---------------------------------------------------------------------------
# Page 1 — Research Radar
# ---------------------------------------------------------------------------
if page == "📄 Research Radar":
    if not connected:
        st.error(f"Cannot reach Fuseki at {FUSEKI_ENDPOINT}")
        st.stop()

    papers = fetch_papers(topic_filter)
    if not papers:
        st.warning("No papers found.")
        st.stop()

    paper_map   = {p["title"]: p for p in papers}
    col_l, col_r = st.columns([1, 2], gap="large")

    with col_l:
        selected = st.selectbox("Select a paper", list(paper_map.keys()),
                                label_visibility="visible")
        p = paper_map[selected]

        topic_color = TOPIC_COLORS.get(p["topic"], DEFAULT_TOPIC_COLOR)
        badge_html  = (f'<span class="badge" style="background:{topic_color}">'
                       f'{p["topic"]}</span>') if p["topic"] else ""

        authors  = fetch_authors(p["uri"])
        auth_str = ", ".join(authors[:5]) + (" …" if len(authors) > 5 else "")

        meta_rows = ""
        if p["year"]:
            meta_rows += f'<div class="meta-row">📅 {p["year"]}</div>'
        if p["venue"]:
            venue_short = p["venue"][:55] + ("…" if len(p["venue"]) > 55 else "")
            meta_rows  += f'<div class="meta-row">📰 {venue_short}</div>'
        if p["citations"]:
            meta_rows += f'<div class="meta-row">📊 {p["citations"]} citations</div>'
        if auth_str:
            meta_rows += f'<div class="meta-row">👥 {auth_str}</div>'

        st.markdown(f"""
        <div class="paper-card">
          <div class="paper-title">{p["title"]}</div>
          {badge_html}
          {meta_rows}
        </div>
        """, unsafe_allow_html=True)

    with col_r:
        # ── Similar papers ──────────────────────────────────────────────────
        st.markdown('<div class="section-header">Similar Papers</div>',
                    unsafe_allow_html=True)
        similar = fetch_similar(p["uri"])
        if similar:
            rows_html = ""
            for s in similar:
                pct   = int(s["score"] * 100)
                title = s["title"][:90] + ("…" if len(s["title"]) > 90 else "")
                rows_html += f"""
                <div class="sim-row">
                  <span class="sim-title">{title}</span>
                  <span class="sim-score">{s['score']:.2f}</span>
                  <div class="sim-bar-bg">
                    <div class="sim-bar-fill" style="width:{pct}%"></div>
                  </div>
                </div>"""
            st.markdown(rows_html, unsafe_allow_html=True)
        else:
            st.info("No similar papers found above threshold.")

        # ── Acknowledged entities ────────────────────────────────────────────
        st.markdown('<div class="section-header">Acknowledged Entities</div>',
                    unsafe_allow_html=True)
        entities = fetch_entities(p["uri"])
        pers  = [e for e in entities if e["type"] == "PER"]
        orgs_ = [e for e in entities if e["type"] == "ORG"]

        if entities:
            if pers:
                chips = "".join(f'<span class="chip-per">{e["name"]}</span>' for e in pers)
                st.markdown(f'<div style="margin-bottom:0.5rem"><b>Persons</b><br>{chips}</div>',
                            unsafe_allow_html=True)
            if orgs_:
                chips = "".join(f'<span class="chip-org">{e["name"]}</span>' for e in orgs_)
                st.markdown(f'<div><b>Organizations</b><br>{chips}</div>',
                            unsafe_allow_html=True)
        else:
            st.info("No acknowledgements extracted for this paper.")


# ---------------------------------------------------------------------------
# Page 2 — Landscape Explorer
# ---------------------------------------------------------------------------
else:
    if not connected:
        st.error(f"Cannot reach Fuseki at {FUSEKI_ENDPOINT}")
        st.stop()

    st.markdown("### 🕸️ Landscape Explorer")

    data = fetch_graph_data(sim_threshold, show_persons)

    # pyvis dark-friendly background matching Streamlit dark theme
    net = Network(height="700px", width="100%",
                  bgcolor="#0e1117", font_color="#e5e7eb")
    net.barnes_hut(gravity=-6000, central_gravity=0.25,
                   spring_length=180, spring_strength=0.04,
                   damping=0.09)

    added: set[str] = set()

    def add_node(nid, label, color, shape="dot", size=22, title=""):
        if nid not in added:
            net.add_node(nid, label=label, color=color,
                         shape=shape, size=size, title=title,
                         font={"size": 11, "color": "#e5e7eb"})
            added.add(nid)

    def short(title: str, n: int = 4) -> str:
        return " ".join(title.split()[:n])

    paper_uris: set[str] = set()

    if show_papers:
        for r in data["papers"]:
            uri   = val(r, "paper")
            title = val(r, "title")
            topic = val(r, "topic")
            paper_uris.add(uri)
            color = TOPIC_COLORS.get(topic, "#94a3b8")
            add_node(uri, short(title), color,
                     shape="dot", size=22, title=title)

            if show_topics and topic:
                tid = f"topic::{topic}"
                add_node(tid, topic, "#fbbf24",
                         shape="diamond", size=28, title=topic)
                net.add_edge(uri, tid,
                             color={"color": "#374151", "opacity": 0.7},
                             width=1, dashes=False)

    for r in data["sims"]:
        p1, p2 = val(r, "p1"), val(r, "p2")
        score  = float(val(r, "score", "0"))
        if p1 in added and p2 in added:
            net.add_edge(p1, p2,
                         color={"color": "#3b82f6", "opacity": 0.6},
                         width=max(1, round(score * 4)),
                         dashes=True,
                         title=f"similarity: {score:.2f}")

    if show_orgs:
        for r in data["orgs"]:
            paper, name = val(r, "paper"), val(r, "name")
            if paper in added:
                oid = f"org::{name}"
                add_node(oid, name[:18], "#22c55e",
                         shape="square", size=14,
                         title=f"Organization: {name}")
                net.add_edge(paper, oid,
                             color={"color": "#16a34a", "opacity": 0.5},
                             width=1, dashes=False)

    if show_persons:
        for r in data["persons"]:
            paper, name = val(r, "paper"), val(r, "name")
            if paper in added:
                pid2 = f"per::{name}"
                add_node(pid2, name.split()[-1], "#ef4444",
                         shape="dot", size=9,
                         title=f"Person: {name}")
                net.add_edge(paper, pid2,
                             color={"color": "#dc2626", "opacity": 0.4},
                             width=1, dashes=False)

    # Write to temp file and serve via data URI (replaces st.components.v1.html)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w",
                                     encoding="utf-8") as f:
        net.save_graph(f.name)
        html_content = open(f.name, encoding="utf-8").read()
    os.unlink(f.name)

    b64 = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    src = f"data:text/html;base64,{b64}"
    st.iframe(src, height=710)

    st.caption(
        f"**{len(added)} nodes** shown · "
        f"similarity ≥ {sim_threshold:.2f} · "
        f"{'persons visible' if show_persons else 'persons hidden'}"
    )