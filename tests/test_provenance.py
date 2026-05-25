from pathlib import Path

from rdflib import Graph, RDF, Namespace


ROOT = Path(__file__).resolve().parents[1]
PROV = Namespace("http://www.w3.org/ns/prov#")


def test_provenance_file_is_valid_turtle():
    graph = Graph()
    graph.parse(ROOT / "provenance/sample_run.ttl", format="turtle")

    assert len(graph) > 0


def test_provenance_contains_entities_activities_and_agents():
    graph = Graph()
    graph.parse(ROOT / "provenance/sample_run.ttl", format="turtle")

    entities = list(graph.subjects(RDF.type, PROV.Entity))
    activities = list(graph.subjects(RDF.type, PROV.Activity))
    agents = list(graph.subjects(RDF.type, PROV.Agent))

    assert len(entities) > 0
    assert len(activities) > 0
    assert len(agents) > 0