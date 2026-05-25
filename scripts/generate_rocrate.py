"""
scripts/generate_rocrate.py — Phase 8
Generates ro-crate-metadata.json using the rocrate library.
"""

import os
from pathlib import Path
from rocrate.rocrate import ROCrate
from rocrate.model import Person

crate = ROCrate()

# Authors
author = crate.add(Person(crate, "https://github.com/kinib0m-dev",
                          {"name": "AI Research KG Group"}))

# Root dataset metadata
crate.root_dataset["name"]        = "AI/ML Research Knowledge Graph"
crate.root_dataset["description"] = (
    "A reproducible open science pipeline that processes 30 landmark AI/ML "
    "papers, runs NLP models (NER, topic modelling, semantic similarity), and "
    "builds a Knowledge Graph in RDF. Built for the Open Science and AI in "
    "Research Software Engineering course at Universidad Politécnica de Madrid."
)
crate.root_dataset["license"]     = "https://spdx.org/licenses/MIT"
crate.root_dataset["author"]      = [author]
crate.root_dataset["version"]     = "0.1.0"
crate.root_dataset["keywords"]    = [
    "knowledge graph", "RDF", "NLP", "NER", "topic modelling",
    "semantic similarity", "open science", "HuggingFace", "ArXiv",
]

# Scripts
scripts = [
    ("scripts/papers.py",              "Download PDFs from ArXiv"),
    ("scripts/process_grobid.py",      "Parse TEI XML from Grobid and extract metadata"),
    ("scripts/evaluate_models.py",     "Evaluate NLP models against gold standard"),
    ("scripts/ner.py",                 "Named entity recognition on acknowledgements"),
    ("scripts/topics.py",              "Zero-shot topic classification"),
    ("scripts/similarity.py",          "Pairwise semantic similarity computation"),
    ("scripts/build_kg.py",            "Build and serialise the RDF Knowledge Graph"),
    ("scripts/generate_provenance.py", "Generate PROV-O provenance record"),
    ("scripts/generate_rocrate.py",    "Generate RO-Crate metadata"),
]

for path, description in scripts:
    if os.path.exists(path):
        crate.add_file(path, properties={
            "@type":       ["File", "SoftwareSourceCode"],
            "description": description,
            "author":      [author],
            "programmingLanguage": {"@id": "https://www.python.org/"},
        })

# Data files
data_files = [
    ("data/gold_standard.json",              "Manual annotations for 10 papers"),
    ("data/processed/papers.json",           "Extracted paper metadata (30 papers)"),
    ("data/processed/model_evaluation.json", "NLP model evaluation results"),
    ("data/processed/ner_results.json",      "NER results for all 30 papers"),
    ("data/processed/topic_results.json",    "Topic classification results"),
    ("data/processed/similarity_results.json","Similarity results for all paper pairs"),
    ("data/knowledge_graph.ttl",             "RDF Knowledge Graph in Turtle format"),
]

for path, description in data_files:
    if os.path.exists(path):
        crate.add_file(path, properties={
            "description": description,
            "author":      [author],
        })

# Provenance
if os.path.exists("provenance/sample_run.ttl"):
    crate.add_file("provenance/sample_run.ttl", properties={
        "@type":       ["File"],
        "description": "PROV-O record of one full pipeline execution",
        "conformsTo":  {"@id": "https://www.w3.org/TR/prov-o/"},
    })

# App
if os.path.exists("app/streamlit_app.py"):
    crate.add_file("app/streamlit_app.py", properties={
        "@type":       ["File", "SoftwareSourceCode"],
        "description": "Streamlit interactive demo app (Research Radar + Landscape Explorer)",
        "author":      [author],
    })

# Config files
for path, desc in [
    ("pyproject.toml",    "Poetry project and dependency configuration"),
    ("docker-compose.yml","Docker Compose configuration for Fuseki"),
    ("README.md",         "Project documentation"),
]:
    if os.path.exists(path):
        crate.add_file(path, properties={"description": desc})

# Write
import tempfile, shutil
 
with tempfile.TemporaryDirectory() as tmp:
    crate.write(tmp)
    src = Path(tmp) / "ro-crate-metadata.json"
    dst = Path("ro-crate-metadata.json")
    shutil.copy(src, dst)
 
print("Saved → ro-crate-metadata.json")