"""
scripts/generate_provenance.py — Phase 8
Generates provenance/sample_run.ttl using the W3C PROV model.
"""

import os
from datetime import datetime, timezone
from prov.model import ProvDocument

doc = ProvDocument()
doc.add_namespace("ex",       "http://example.org/aikg/")
doc.add_namespace("prov",     "http://www.w3.org/ns/prov#")
doc.add_namespace("foaf",     "http://xmlns.com/foaf/0.1/")
doc.add_namespace("xsd",      "http://www.w3.org/2001/XMLSchema#")
doc.add_namespace("agent",    "http://example.org/aikg/prov/agent/")
doc.add_namespace("entity",   "http://example.org/aikg/prov/entity/")
doc.add_namespace("activity", "http://example.org/aikg/prov/activity/")

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = doc.agent("agent:researcher", {"foaf:name": "AI Research KG Group"})

# ---------------------------------------------------------------------------
# Entities — inputs
# ---------------------------------------------------------------------------
e_pdfs = doc.entity("entity:input_pdfs", {
    "prov:label":    "30 ArXiv AI/ML PDFs",
    "prov:type":     "prov:Collection",
    "ex:paperCount": 30,
    "ex:source":     "https://arxiv.org",
})
e_gold = doc.entity("entity:gold_standard", {
    "prov:label": "Gold standard annotations (10 papers)",
    "ex:path":    "data/gold_standard.json",
})

# ---------------------------------------------------------------------------
# Entities — intermediate
# ---------------------------------------------------------------------------
e_papers = doc.entity("entity:papers_json", {
    "prov:label": "Extracted paper metadata",
    "ex:path":    "data/processed/papers.json",
    "ex:records": 30,
})
e_eval = doc.entity("entity:model_evaluation_json", {
    "prov:label": "Model evaluation results",
    "ex:path":    "data/processed/model_evaluation.json",
})
e_ner = doc.entity("entity:ner_results_json", {
    "prov:label": "NER results",
    "ex:path":    "data/processed/ner_results.json",
    "ex:model":   "Jean-Baptiste/roberta-large-ner-english",
    "ex:f1":      0.469,
})
e_topics = doc.entity("entity:topic_results_json", {
    "prov:label":   "Topic classification results",
    "ex:path":      "data/processed/topic_results.json",
    "ex:model":     "facebook/bart-large-mnli",
    "ex:accuracy":  0.6,
})
e_sim = doc.entity("entity:similarity_results_json", {
    "prov:label":      "Similarity results",
    "ex:path":         "data/processed/similarity_results.json",
    "ex:model":        "sentence-transformers/all-mpnet-base-v2",
    "ex:threshold":    0.35,
    "ex:totalPairs":   406,
    "ex:similarPairs": 178,
})

# ---------------------------------------------------------------------------
# Entities — final output
# ---------------------------------------------------------------------------
e_kg = doc.entity("entity:knowledge_graph_ttl", {
    "prov:label": "RDF Knowledge Graph (Turtle)",
    "ex:path":    "data/knowledge_graph.ttl",
    "ex:triples": 2151,
    "ex:format":  "text/turtle",
})

# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------
t = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

act_grobid = doc.activity("activity:grobid_extraction",
    t("2026-05-01T10:00:00"), t("2026-05-01T10:15:00"), {
        "prov:label": "Grobid PDF parsing",
        "ex:script":  "scripts/process_grobid.py",
        "ex:tool":    "lfoppiano/grobid:0.8.2",
    })
act_eval = doc.activity("activity:model_evaluation",
    t("2026-05-01T10:20:00"), t("2026-05-01T10:50:00"), {
        "prov:label": "NLP model evaluation against gold standard",
        "ex:script":  "scripts/evaluate_models.py",
    })
act_ner = doc.activity("activity:ner_extraction",
    t("2026-05-01T11:00:00"), t("2026-05-01T11:20:00"), {
        "prov:label": "Named entity recognition on all 30 papers",
        "ex:script":  "scripts/ner.py",
        "ex:model":   "Jean-Baptiste/roberta-large-ner-english",
    })
act_topics = doc.activity("activity:topic_classification",
    t("2026-05-01T11:20:00"), t("2026-05-01T11:35:00"), {
        "prov:label": "Zero-shot topic classification on all 30 papers",
        "ex:script":  "scripts/topics.py",
        "ex:model":   "facebook/bart-large-mnli",
    })
act_sim = doc.activity("activity:similarity_computation",
    t("2026-05-01T11:35:00"), t("2026-05-01T11:55:00"), {
        "prov:label": "Pairwise semantic similarity on all 30 papers",
        "ex:script":  "scripts/similarity.py",
        "ex:model":   "sentence-transformers/all-mpnet-base-v2",
    })
act_kg = doc.activity("activity:kg_construction",
    t("2026-05-01T12:00:00"), t("2026-05-01T12:10:00"), {
        "prov:label":     "Knowledge Graph construction and enrichment",
        "ex:script":      "scripts/build_kg.py",
        "ex:enrichment1": "OpenAlex API",
        "ex:enrichment2": "Wikidata SPARQL",
    })

# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------
doc.wasGeneratedBy(e_papers, act_grobid)
doc.used(act_grobid, e_pdfs)
doc.wasAssociatedWith(act_grobid, agent)

doc.wasGeneratedBy(e_eval, act_eval)
doc.used(act_eval, e_papers)
doc.used(act_eval, e_gold)
doc.wasAssociatedWith(act_eval, agent)

doc.wasGeneratedBy(e_ner, act_ner)
doc.used(act_ner, e_papers)
doc.wasDerivedFrom(e_ner, e_eval)
doc.wasAssociatedWith(act_ner, agent)

doc.wasGeneratedBy(e_topics, act_topics)
doc.used(act_topics, e_papers)
doc.wasDerivedFrom(e_topics, e_eval)
doc.wasAssociatedWith(act_topics, agent)

doc.wasGeneratedBy(e_sim, act_sim)
doc.used(act_sim, e_papers)
doc.wasDerivedFrom(e_sim, e_eval)
doc.wasAssociatedWith(act_sim, agent)

doc.wasGeneratedBy(e_kg, act_kg)
doc.used(act_kg, e_papers)
doc.used(act_kg, e_ner)
doc.used(act_kg, e_topics)
doc.used(act_kg, e_sim)
doc.wasAssociatedWith(act_kg, agent)

# ---------------------------------------------------------------------------
# Serialize
# ---------------------------------------------------------------------------
os.makedirs("provenance", exist_ok=True)
output = "provenance/sample_run.ttl"
with open(output, "wb") as f:
    doc.serialize(f, format="rdf", rdf_format="turtle")
print(f"Saved → {output}")