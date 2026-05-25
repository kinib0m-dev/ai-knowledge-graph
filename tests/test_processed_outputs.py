import json
from pathlib import Path

from rdflib import Graph, RDF
from scripts.build_kg import EX


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_papers_dataset_has_30_papers():
    papers = load_json(ROOT / "data/processed/papers.json")

    assert len(papers) == 30

    for paper in papers:
        assert "id" in paper
        assert "title" in paper
        assert "abstract" in paper
        assert "authors" in paper
        assert "acknowledgements" in paper

        assert paper["id"]
        assert paper["title"]
        assert isinstance(paper["authors"], list)


def test_topic_results_exist_for_30_papers():
    topics = load_json(ROOT / "data/processed/topic_results.json")

    assert len(topics) == 30

    for result in topics:
        assert "id" in result
        assert "title" in result
        assert "topic" in result


def test_ner_results_exist_for_30_papers():
    ner_results = load_json(ROOT / "data/processed/ner_results.json")

    assert len(ner_results) == 30

    for result in ner_results:
        assert "id" in result
        assert "entities" in result
        assert "PER" in result["entities"]
        assert "ORG" in result["entities"]
        assert "PROJECT" in result["entities"]


def test_similarity_results_are_valid():
    similarity = load_json(ROOT / "data/processed/similarity_results.json")

    assert "threshold" in similarity
    assert "total_pairs" in similarity
    assert "similar_pairs" in similarity
    assert "pairs" in similarity
    assert "similar" in similarity

    assert similarity["total_pairs"] == len(similarity["pairs"])
    assert similarity["similar_pairs"] == len(similarity["similar"])

    for pair in similarity["pairs"]:
        assert "paper1" in pair
        assert "paper2" in pair
        assert "score" in pair
        assert 0 <= pair["score"] <= 1


def test_knowledge_graph_is_valid_turtle():
    graph = Graph()
    graph.parse(ROOT / "data/knowledge_graph.ttl", format="turtle")

    assert len(graph) > 0

    papers = list(graph.subjects(RDF.type, EX.Paper))
    similarities = list(graph.subjects(RDF.type, EX.SimilarityStatement))

    assert len(papers) == 30
    assert len(similarities) > 0