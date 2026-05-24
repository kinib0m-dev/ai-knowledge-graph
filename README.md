# AI/ML Research Knowledge Graph

A reproducible open science pipeline that processes 30 landmark AI/ML papers, runs NLP models on them, and builds a Knowledge Graph in RDF. Built as Deliverable 2 for the _Open Science and AI in Research Software Engineering_ course at Universidad Politécnica de Madrid.

---

## Overview

The pipeline takes 30 ArXiv papers as input and produces a SPARQL-queryable Knowledge Graph enriched with external data. A Streamlit app allows interactive exploration.

```
PDFs → Grobid → NLP models (HuggingFace) → RDF Knowledge Graph → Fuseki → Streamlit app
```

**NLP tasks:**

- **Topic modelling** — `facebook/bart-large-mnli` (zero-shot classification)
- **Similarity** — `sentence-transformers/all-mpnet-base-v2` (cosine similarity)
- **NER** — `Jean-Baptiste/roberta-large-ner-english` (persons and organisations from acknowledgements)

**External enrichment:**

- [OpenAlex API](https://openalex.org/) — citation count, publication year, venue
- [Wikidata SPARQL](https://query.wikidata.org/) — country and website of organisations

---

## Requirements

- Python 3.11–3.14
- [Poetry](https://python-poetry.org/)
- [Docker](https://www.docker.com/) (for Grobid and Fuseki)

---

## Installation

```bash
git clone https://github.com/<your-org>/ai-knowledge-graph.git
cd ai-knowledge-graph
poetry install --no-root
```

Copy `.env.example` to `.env` and set your HuggingFace token:

```bash
cp .env.example .env
# edit .env and set HF_TOKEN=hf_...
```

---

## Running the pipeline

All steps assume you are inside the project root with the Poetry environment active (`poetry shell` or prefix each command with `poetry run`).

### 1. Start Grobid

```bash
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.2
```

### 2. Download and parse papers

```bash
poetry run python scripts/papers.py
poetry run python scripts/process_grobid.py
```

Outputs: `data/processed/papers.json`

### 3. Evaluate and select NLP models

```bash
poetry run python scripts/evaluate_models.py
```

Outputs: `data/processed/model_evaluation.json`

### 4. Run NLP models on all 30 papers

```bash
poetry run python scripts/topics.py
poetry run python scripts/similarity.py
poetry run python scripts/ner.py
```

Outputs: `data/processed/topic_results.json`, `similarity_results.json`, `ner_results.json`

### 5. Build the Knowledge Graph

```bash
poetry run python scripts/build_kg.py
```

Outputs: `data/knowledge_graph.ttl`

> **Note:** Wikidata enrichment requires network access to `query.wikidata.org`. Use `--skip-wikidata` to build offline.

### 6. Load into Fuseki and run the app

```bash
docker compose up -d
poetry run streamlit run app/streamlit_app.py
```

---

## Project structure

```
ai-knowledge-graph/
├── scripts/
│   ├── papers.py             # Download PDFs from ArXiv
│   ├── process_grobid.py     # Parse TEI XML from Grobid
│   ├── evaluate_models.py    # Evaluate candidate NLP models against gold standard
│   ├── topics.py             # Zero-shot topic classification (bart-large-mnli)
│   ├── similarity.py         # Pairwise semantic similarity (all-mpnet-base-v2)
│   ├── ner.py                # Named entity recognition (roberta-large-ner-english)
│   └── build_kg.py           # Build and serialise the RDF Knowledge Graph
├── app/
│   └── streamlit_app.py      # Interactive demo (Research Radar + Landscape Explorer)
├── data/
│   ├── papers/               # Downloaded PDFs (not tracked in git)
│   ├── grobid_output/        # TEI XML files (not tracked in git)
│   ├── gold_standard.json    # Manual annotations for 10 papers
│   ├── processed/            # JSON outputs of each pipeline stage
│   └── knowledge_graph.ttl   # Final RDF output
├── provenance/
│   └── sample_run.ttl        # PROV-O record of one pipeline execution
├── tests/
├── pyproject.toml
└── ro-crate-metadata.json    # RO-Crate research object metadata
```

---

## Knowledge Graph model

Base terms: `Paper`, `Person`, `Organization`, `Topic`

Base properties: `ex:belongsToTopic`, `ex:similarTo`, `dc:title`, `foaf:name`, `ex:acknowledges`

External properties (≥5 from external KGs):

| Property           | Source          | Type |
| ------------------ | --------------- | ---- |
| `ex:citationCount` | OpenAlex API    | API  |
| `dc:date` (year)   | OpenAlex API    | API  |
| `ex:venue`         | OpenAlex API    | API  |
| `ex:openalexId`    | OpenAlex API    | API  |
| `ex:country`       | Wikidata SPARQL | RDF  |
| `foaf:homepage`    | Wikidata SPARQL | RDF  |

Namespaces used: `dc`, `foaf`, `skos`, `org`, `owl`, `xsd`, and a custom `ex:` namespace.

---

## Model decisions

| Task       | Winner                                               | Runner-up                                          | Metric   |
| ---------- | ---------------------------------------------------- | -------------------------------------------------- | -------- |
| NER        | `Jean-Baptiste/roberta-large-ner-english` (F1=0.469) | `dslim/bert-base-NER` (F1=0.264)                   | F1       |
| Topic      | `facebook/bart-large-mnli` (Acc=0.6)                 | `typeform/distilbert-base-uncased-mnli` (Acc=0.5)  | Accuracy |
| Similarity | `sentence-transformers/all-mpnet-base-v2` (F1=0.364) | `sentence-transformers/all-MiniLM-L6-v2` (F1=0.25) | F1       |

Models were evaluated against a gold standard of 10 manually annotated papers. See `data/gold_standard.json` and `data/processed/model_evaluation.json`.

---

## License

MIT
