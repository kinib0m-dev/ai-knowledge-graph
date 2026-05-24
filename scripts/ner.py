import os
import json
import requests
import time
from pathlib import Path

HF_TOKEN = os.environ.get("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
MODEL = "Jean-Baptiste/roberta-large-ner-english"
URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}"
PROCESSED_PATH = Path("data/processed/papers.json")
OUTPUT_PATH = Path("data/processed/ner_results.json")


def hf_ner(text: str, retries: int = 5) -> list:
    for i in range(retries):
        response = requests.post(URL, headers=HEADERS, json={"inputs": text[:512]})
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503:
            wait = 20 * (i + 1)
            print(f"  Model loading, retrying in {wait}s...")
            time.sleep(wait)
        else:
            print(f"  ERROR {response.status_code}: {response.text[:200]}")
            return []
    return []


def extract_entities(raw: list) -> dict:
    entities = {"PER": [], "ORG": [], "PROJECT": []}
    if not raw or not isinstance(raw, list):
        return entities

    items = raw[0] if isinstance(raw[0], list) else raw
    seen = set()
    for ent in items:
        label = ent.get("entity_group", "")
        word = ent.get("word", "").strip()
        if not word or word in seen:
            continue
        seen.add(word)
        if label == "PER":
            entities["PER"].append(word)
        elif label == "ORG":
            entities["ORG"].append(word)

    return entities


def main():
    papers = json.loads(PROCESSED_PATH.read_text())
    results = []

    for i, paper in enumerate(papers):
        print(f"[{i+1}/30] {paper['title'][:50]}")
        if not paper["acknowledgements"]:
            print("  No acknowledgements, skipping.")
            results.append({"id": paper["id"], "title": paper["title"], "entities": {"PER": [], "ORG": [], "PROJECT": []}})
            continue

        raw = hf_ner(paper["acknowledgements"])
        entities = extract_entities(raw)
        print(f"  PER: {entities['PER'][:3]} ORG: {entities['ORG'][:3]}")
        results.append({"id": paper["id"], "title": paper["title"], "entities": entities})
        time.sleep(1)

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nDone. Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
