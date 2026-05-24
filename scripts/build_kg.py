"""
build_kg.py — Phase 5: Build the RDF Knowledge Graph.

Loads processed data (papers, NER, topics, similarity), enriches with:
  - OpenAlex API (citation count, publication year, venue, OpenAlex ID)
  - Wikidata SPARQL (country and website of recognised organisations)

Serialises the result to data/knowledge_graph.ttl.
"""

import json
import os
import time
import requests
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, XSD
from rdflib.namespace import DC, FOAF, SKOS, OWL
from SPARQLWrapper import SPARQLWrapper, JSON

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------
EX   = Namespace("http://example.org/aikg/")
ORG  = Namespace("http://www.w3.org/ns/org#")
PROV = Namespace("http://www.w3.org/ns/prov#")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slug(text: str) -> str:
    """Turn a string into a safe URI fragment."""
    return (text.strip()
                .replace(" ", "_")
                .replace("/", "-")
                .replace(":", "")
                .replace(".", "")
                .replace(",", ""))


def load_json(path: str):
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# OpenAlex enrichment  (API source ✓)
# ---------------------------------------------------------------------------
OPENALEX_BASE = "https://api.openalex.org/works/arxiv:"

def fetch_openalex(arxiv_id: str) -> dict:
    """Return citation_count, year, venue_name, openalex_id or empty dict."""
    url = OPENALEX_BASE + arxiv_id
    try:
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "aikg/1.0 (mailto:student@upm.es)"})
        if r.status_code != 200:
            return {}
        data = r.json()
        venue = ""
        if data.get("primary_location") and data["primary_location"].get("source"):
            venue = data["primary_location"]["source"].get("display_name", "")
        return {
            "openalex_id":     data.get("id", ""),
            "citation_count":  data.get("cited_by_count", 0),
            "year":            data.get("publication_year"),
            "venue":           venue,
        }
    except Exception as e:
        print(f"  [OpenAlex] error for {arxiv_id}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Wikidata enrichment  (RDF/SPARQL source ✓)
# ---------------------------------------------------------------------------
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Cache to avoid redundant queries for the same org name
_wikidata_cache: dict[str, dict] = {}

def fetch_wikidata_org(org_name: str) -> dict:
    """Return country and website for an organisation from Wikidata."""
    if org_name in _wikidata_cache:
        return _wikidata_cache[org_name]

    sparql = SPARQLWrapper(WIKIDATA_ENDPOINT)
    sparql.addCustomHttpHeader("User-Agent", "aikg/1.0 (mailto:student@upm.es)")
    query = f"""
    SELECT ?country ?countryLabel ?website WHERE {{
      ?org wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      ?org rdfs:label "{org_name}"@en .
      OPTIONAL {{ ?org wdt:P17 ?countryItem .
                 ?countryItem rdfs:label ?countryLabel .
                 FILTER(LANG(?countryLabel) = "en") }}
      OPTIONAL {{ ?org wdt:P856 ?website . }}
      BIND(?countryItem AS ?country)
    }} LIMIT 1
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    result = {}
    try:
        data = sparql.query().convert()
        bindings = data["results"]["bindings"]
        if bindings:
            b = bindings[0]
            result["country"] = b.get("countryLabel", {}).get("value", "")
            result["website"] = b.get("website", {}).get("value", "")
    except Exception as e:
        print(f"  [Wikidata] error for '{org_name}': {e}")

    _wikidata_cache[org_name] = result
    time.sleep(0.5)   # polite rate limiting
    return result


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------
def build_graph(data_dir: str = "data") -> Graph:
    g = Graph()
    g.bind("ex",   EX)
    g.bind("dc",   DC)
    g.bind("foaf", FOAF)
    g.bind("skos", SKOS)
    g.bind("org",  ORG)
    g.bind("owl",  OWL)
    g.bind("xsd",  XSD)

    processed = os.path.join(data_dir, "processed")
    papers      = load_json(os.path.join(processed, "papers.json"))
    ner_list    = load_json(os.path.join(processed, "ner_results.json"))
    topic_list  = load_json(os.path.join(processed, "topic_results.json"))
    sim_data    = load_json(os.path.join(processed, "similarity_results.json"))

    # Index by paper id
    ner_by_id   = {e["id"]: e["entities"] for e in ner_list}
    topic_by_id = {e["id"]: e.get("topic") for e in topic_list}
    sim_pairs   = [p for p in sim_data["pairs"]
                   if p["score"] >= sim_data["threshold"]]

    # Track created topics / persons / orgs to avoid duplicates
    topics_created: set[str] = set()
    persons_created: set[str] = set()
    orgs_created: set[str] = set()

    # -----------------------------------------------------------------------
    # Papers
    # -----------------------------------------------------------------------
    for paper in papers:
        pid   = paper["id"]
        p_uri = EX[f"paper/{pid}"]

        g.add((p_uri, RDF.type, EX.Paper))
        g.add((p_uri, DC.title,      Literal(paper["title"])))
        g.add((p_uri, DC.identifier, Literal(pid)))
        g.add((p_uri, OWL.sameAs,
               URIRef(f"https://arxiv.org/abs/{pid}")))

        if paper.get("abstract"):
            g.add((p_uri, DC.description, Literal(paper["abstract"])))

        if paper.get("authors"):
            for author in paper["authors"]:
                g.add((p_uri, DC.creator, Literal(author)))

        # --- Topic ---
        topic_label = topic_by_id.get(pid)
        if topic_label:
            t_uri = EX[f"topic/{slug(topic_label)}"]
            if topic_label not in topics_created:
                g.add((t_uri, RDF.type, SKOS.Concept))
                g.add((t_uri, SKOS.prefLabel, Literal(topic_label)))
                topics_created.add(topic_label)
            g.add((p_uri, EX.belongsToTopic, t_uri))

        # --- NER: persons & organisations ---
        entities = ner_by_id.get(pid, {})

        for person_name in entities.get("PER", []):
            person_name = person_name.strip()
            if not person_name or person_name == ".":
                continue
            per_uri = EX[f"person/{slug(person_name)}"]
            if person_name not in persons_created:
                g.add((per_uri, RDF.type, FOAF.Person))
                g.add((per_uri, FOAF.name, Literal(person_name)))
                persons_created.add(person_name)
            g.add((p_uri, EX.acknowledges, per_uri))

        for org_name in entities.get("ORG", []):
            org_name = org_name.strip()
            if not org_name:
                continue
            org_uri = EX[f"organization/{slug(org_name)}"]
            if org_name not in orgs_created:
                g.add((org_uri, RDF.type, ORG.Organization))
                g.add((org_uri, FOAF.name, Literal(org_name)))

                # Wikidata enrichment
                wd = fetch_wikidata_org(org_name)
                if wd.get("country"):
                    g.add((org_uri, EX.country, Literal(wd["country"])))
                if wd.get("website"):
                    g.add((org_uri, FOAF.homepage, URIRef(wd["website"])))

                orgs_created.add(org_name)
            g.add((p_uri, EX.acknowledges, org_uri))

        # --- OpenAlex enrichment ---
        print(f"  Fetching OpenAlex for {pid}…")
        oa = fetch_openalex(pid)
        if oa.get("openalex_id"):
            g.add((p_uri, EX.openalexId, URIRef(oa["openalex_id"])))
        if oa.get("citation_count") is not None:
            g.add((p_uri, EX.citationCount,
                   Literal(oa["citation_count"], datatype=XSD.integer)))
        if oa.get("year"):
            g.add((p_uri, DC.date,
                   Literal(str(oa["year"]), datatype=XSD.gYear)))
        if oa.get("venue"):
            g.add((p_uri, EX.venue, Literal(oa["venue"])))

        time.sleep(0.2)   # OpenAlex rate limit

    # -----------------------------------------------------------------------
    # Similarity pairs
    # -----------------------------------------------------------------------
    for pair in sim_pairs:
        p1_uri = EX[f"paper/{pair['paper1']}"]
        p2_uri = EX[f"paper/{pair['paper2']}"]
        score  = round(pair["score"], 4)

        # Reified similarity statement so we can attach the score
        sim_uri = EX[f"similarity/{pair['paper1']}_{pair['paper2']}"]
        g.add((sim_uri, RDF.type,       EX.SimilarityStatement))
        g.add((sim_uri, EX.paper1,      p1_uri))
        g.add((sim_uri, EX.paper2,      p2_uri))
        g.add((sim_uri, EX.similarityScore,
               Literal(score, datatype=XSD.decimal)))

        # Also add a direct edge for easy SPARQL traversal
        g.add((p1_uri, EX.similarTo, p2_uri))

    print(f"\nGraph built: {len(g)} triples.")
    return g


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the AI/ML papers Knowledge Graph.")
    parser.add_argument("--data-dir", default="data",
                        help="Root data directory (default: data)")
    parser.add_argument("--output",   default="data/knowledge_graph.ttl",
                        help="Output Turtle file (default: data/knowledge_graph.ttl)")
    parser.add_argument("--skip-wikidata", action="store_true",
                        help="Skip Wikidata queries (useful for offline testing)")
    args = parser.parse_args()

    if args.skip_wikidata:
        # Monkey-patch to a no-op
        import build_kg as _self
        _self.fetch_wikidata_org = lambda name: {}

    g = build_graph(data_dir=args.data_dir)
    g.serialize(destination=args.output, format="turtle")
    print(f"Saved → {args.output}")