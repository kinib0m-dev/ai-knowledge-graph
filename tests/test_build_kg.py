import json
from pathlib import Path

from rdflib import RDF, Literal, URIRef
from rdflib.namespace import DC, FOAF, SKOS

from scripts import build_kg


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_slug_generates_safe_uri_fragment():
    assert build_kg.slug("Universidad Politécnica de Madrid") == "Universidad_Politécnica_de_Madrid"
    assert build_kg.slug("AI/ML: Test, Paper.") == "AI-ML_Test_Paper"


def test_build_graph_with_mocked_external_sources(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()

    papers = [
        {
            "id": "1234.5678",
            "title": "Paper One",
            "abstract": "This paper is about language models.",
            "authors": ["Alice Smith"],
            "acknowledgements": "Thanks to UPM."
        },
        {
            "id": "9999.9999",
            "title": "Paper Two",
            "abstract": "This paper is about transformers.",
            "authors": ["Bob Jones"],
            "acknowledgements": ""
        }
    ]

    ner_results = [
        {
            "id": "1234.5678",
            "title": "Paper One",
            "entities": {
                "PER": ["Alice"],
                "ORG": ["UPM"],
                "PROJECT": []
            }
        },
        {
            "id": "9999.9999",
            "title": "Paper Two",
            "entities": {
                "PER": [],
                "ORG": [],
                "PROJECT": []
            }
        }
    ]

    topic_results = [
        {
            "id": "1234.5678",
            "title": "Paper One",
            "topic": "Language Models",
            "scores": {}
        },
        {
            "id": "9999.9999",
            "title": "Paper Two",
            "topic": "Language Models",
            "scores": {}
        }
    ]

    similarity_results = {
        "threshold": 0.35,
        "total_pairs": 1,
        "similar_pairs": 1,
        "pairs": [
            {
                "paper1": "1234.5678",
                "paper2": "9999.9999",
                "score": 0.75
            }
        ],
        "similar": [
            {
                "paper1": "1234.5678",
                "paper2": "9999.9999",
                "score": 0.75
            }
        ]
    }

    write_json(processed / "papers.json", papers)
    write_json(processed / "ner_results.json", ner_results)
    write_json(processed / "topic_results.json", topic_results)
    write_json(processed / "similarity_results.json", similarity_results)

    monkeypatch.setattr(
        build_kg,
        "fetch_openalex",
        lambda arxiv_id: {
            "openalex_id": f"https://openalex.org/W{arxiv_id.replace('.', '')}",
            "citation_count": 10,
            "year": 2024,
            "venue": "Test Venue"
        }
    )

    monkeypatch.setattr(
        build_kg,
        "fetch_wikidata_org",
        lambda org_name: {
            "country": "Spain",
            "website": "https://www.upm.es"
        }
    )

    monkeypatch.setattr(build_kg.time, "sleep", lambda seconds: None)

    graph = build_kg.build_graph(str(tmp_path))

    paper_uri = build_kg.EX["paper/1234.5678"]
    topic_uri = build_kg.EX["topic/Language_Models"]
    org_uri = build_kg.EX["organization/UPM"]

    assert (paper_uri, RDF.type, build_kg.EX.Paper) in graph
    assert (paper_uri, DC.title, Literal("Paper One")) in graph
    assert (paper_uri, build_kg.EX.belongsToTopic, topic_uri) in graph

    assert (topic_uri, RDF.type, SKOS.Concept) in graph
    assert (org_uri, RDF.type, build_kg.ORG.Organization) in graph
    assert (org_uri, build_kg.EX.country, Literal("Spain")) in graph
    assert (org_uri, FOAF.homepage, URIRef("https://www.upm.es")) in graph

    similarities = list(graph.subjects(RDF.type, build_kg.EX.SimilarityStatement))
    assert len(similarities) == 1