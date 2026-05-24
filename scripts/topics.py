import os
import json
import requests
import time
from pathlib import Path

HF_TOKEN = os.environ.get("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
MODEL = "facebook/bart-large-mnli"
URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}"
PROCESSED_PATH = Path("data/processed/papers.json")
OUTPUT_PATH = Path("data/processed/topic_results.json")

TOPIC_LABELS = [
    "Generative Models",
    "Language Models",
    "Computer Vision",
    "Reinforcement Learning",
    "AI Safety & Ethics",
    "Optimization & Training",
]


def hf_classify(text: str, retries: int = 5) -> dict | None:
    for i in range(retries):
        response = requests.post(URL, headers=HEADERS, json={
            "inputs": text[:512],
            "parameters": {"candidate_labels": TOPIC_LABELS}
        })
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503:
            wait = 20 * (i + 1)
            print(f"  Model loading, retrying in {wait}s...")
            time.sleep(wait)
        else:
            print(f"  ERROR {response.status_code}: {response.text[:200]}")
            return None
    return None


def main():
    papers = json.loads(PROCESSED_PATH.read_text())
    results = []

    for i, paper in enumerate(papers):
        print(f"[{i+1}/30] {paper['title'][:50]}")
        if not paper["abstract"]:
            print("  No abstract, skipping.")
            results.append({"id": paper["id"], "title": paper["title"], "topic": None, "scores": {}})
            continue

        result = hf_classify(paper["abstract"])
        if not result:
            results.append({"id": paper["id"], "title": paper["title"], "topic": None, "scores": {}})
            continue

        if isinstance(result, list):
            result = result[0]

        if "labels" in result:
            topic = result["labels"][0]
            scores = dict(zip(result["labels"], result["scores"]))
        elif "label" in result:
            topic = result["label"]
            scores = {"score": result["score"]}
        else:
            topic = None
            scores = {}

        print(f"  → {topic}")
        results.append({"id": paper["id"], "title": paper["title"], "topic": topic, "scores": scores})
        time.sleep(1)

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nDone. Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
