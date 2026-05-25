from scripts.ner import extract_entities


def test_extract_entities_returns_empty_structure_for_empty_input():
    result = extract_entities([])

    assert result == {
        "PER": [],
        "ORG": [],
        "PROJECT": []
    }


def test_extract_entities_detects_persons_and_organizations():
    raw = [
        {"entity_group": "PER", "word": "Alice"},
        {"entity_group": "ORG", "word": "Universidad Politécnica de Madrid"},
        {"entity_group": "PER", "word": "Bob"},
    ]

    result = extract_entities(raw)

    assert "Alice" in result["PER"]
    assert "Bob" in result["PER"]
    assert "Universidad Politécnica de Madrid" in result["ORG"]


def test_extract_entities_removes_duplicates():
    raw = [
        {"entity_group": "PER", "word": "Alice"},
        {"entity_group": "PER", "word": "Alice"},
        {"entity_group": "ORG", "word": "UPM"},
        {"entity_group": "ORG", "word": "UPM"},
    ]

    result = extract_entities(raw)

    assert result["PER"].count("Alice") == 1
    assert result["ORG"].count("UPM") == 1