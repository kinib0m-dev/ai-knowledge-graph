# AI/ML Research Knowledge Graph

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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

- [OpenAlex API](https://openalex.org/). Citation count, publication year, venue, OpenAlex ID
- [Wikidata SPARQL](https://query.wikidata.org/). Country and website of organisations

---

## Requirements

- Python 3.11–3.14
- [Poetry](https://python-poetry.org/)
- [Docker](https://www.docker.com/) (for Grobid and Fuseki)

---

## Installation

```bash
git clone https://github.com/kinib0m-dev/ai-knowledge-graph.git
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

### 1. Start Grobid (different terminal)

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
# Create dataset and upload TTL:
curl -u admin:admin -X POST http://localhost:3030/$/datasets -d "dbName=papers&dbType=tdb2"
curl -u admin:admin -X PUT http://localhost:3030/papers/data \
  -H "Content-Type: text/turtle" --data-binary @data/knowledge_graph.ttl
# Start app:
poetry run streamlit run app/streamlit_app.py
```

### 7. Generate provenance record

```bash
poetry run python scripts/generate_provenance.py
```

Outputs: `provenance/sample_run.ttl`

---

## Project structure

```
ai-knowledge-graph/
├── scripts/
│   ├── papers.py               # Download PDFs from ArXiv
│   ├── process_grobid.py       # Parse TEI XML from Grobid
│   ├── evaluate_models.py      # Evaluate candidate NLP models against gold standard
│   ├── topics.py               # Zero-shot topic classification
│   ├── similarity.py           # Pairwise semantic similarity
│   ├── ner.py                  # Named entity recognition
│   ├── build_kg.py             # Build and serialise the RDF Knowledge Graph
│   └── generate_provenance.py  # Generate PROV-O provenance record
├── app/
│   └── streamlit_app.py        # Interactive demo (Research Radar + Landscape Explorer)
├── data/
│   ├── papers/                 # Downloaded PDFs (not tracked in git)
│   ├── grobid_output/          # TEI XML files (not tracked in git)
│   ├── gold_standard.json      # Manual annotations for 10 papers
│   ├── processed/              # JSON outputs of each pipeline stage
│   └── knowledge_graph.ttl     # Final RDF output
├── provenance/
│   └── sample_run.ttl          # PROV-O record of one pipeline execution
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── ro-crate-metadata.json      # RO-Crate research object metadata
```

---

## Knowledge Graph model

### Terms

| Term                     | Type  | Description                                    |
| ------------------------ | ----- | ---------------------------------------------- |
| `ex:Paper`               | Class | An AI/ML research paper                        |
| `foaf:Person`            | Class | A person acknowledged in a paper               |
| `org:Organization`       | Class | An organisation acknowledged in a paper        |
| `skos:Concept`           | Class | A research topic                               |
| `ex:SimilarityStatement` | Class | Reified similarity relation between two papers |

### Properties

**Base properties (required by spec):**

| Property            | Domain → Range        | Description                                |
| ------------------- | --------------------- | ------------------------------------------ |
| `ex:belongsToTopic` | Paper → Topic         | Topic assigned by zero-shot classification |
| `ex:similarTo`      | Paper → Paper         | Direct similarity edge (above threshold)   |
| `dc:title`          | Paper → string        | Paper title                                |
| `foaf:name`         | Person / Org → string | Entity name                                |
| `ex:acknowledges`   | Paper → Person / Org  | Entities extracted from acknowledgements   |

**Additional properties:**

| Property                  | Domain → Range                | Description                 |
| ------------------------- | ----------------------------- | --------------------------- |
| `dc:identifier`           | Paper → string                | ArXiv ID                    |
| `dc:description`          | Paper → string                | Abstract                    |
| `dc:creator`              | Paper → string                | Author names                |
| `owl:sameAs`              | Paper → URI                   | Link to ArXiv abstract page |
| `ex:paper1` / `ex:paper2` | SimilarityStatement → Paper   | Papers in a similarity pair |
| `ex:similarityScore`      | SimilarityStatement → decimal | Cosine similarity score     |

**External properties (≥5 from external KGs):**

| Property           | Domain → Range        | Source          | Type |
| ------------------ | --------------------- | --------------- | ---- |
| `ex:citationCount` | Paper → integer       | OpenAlex API    | API  |
| `dc:date`          | Paper → gYear         | OpenAlex API    | API  |
| `ex:venue`         | Paper → string        | OpenAlex API    | API  |
| `ex:openalexId`    | Paper → URI           | OpenAlex API    | API  |
| `ex:country`       | Organization → string | Wikidata SPARQL | RDF  |
| `foaf:homepage`    | Organization → URI    | Wikidata SPARQL | RDF  |

**Namespaces:** `dc`, `foaf`, `skos`, `org`, `owl`, `xsd`, and custom `ex: <http://example.org/aikg/>`

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

---

## Related metadata files

| File                        | Purpose                                                            |
| --------------------------- | ------------------------------------------------------------------ |
| `CITATION.cff`              | Citation metadata — used by GitHub's "Cite this repository" button |
| `codemeta.json`             | Software metadata in CodeMeta schema                               |
| `ro-crate-metadata.json`    | RO-Crate research object wrapping all pipeline artifacts           |
| `provenance/sample_run.ttl` | PROV-O record of one full pipeline execution                       |

---

## Citation

If you use this software, please cite it using the metadata in [`CITATION.cff`](CITATION.cff):

```bibtex
@software{aikg2026,
  title   = {AI/ML Research Knowledge Graph},
  author  = {AI Research KG Group},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/kinib0m-dev/ai-knowledge-graph}
}
```
