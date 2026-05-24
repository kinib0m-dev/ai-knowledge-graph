import os
import json
import requests
import time
from pathlib import Path

HF_TOKEN = os.environ.get("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
MODEL = "sentence-transformers/all-mpnet-base-v2"
URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}"
PROCESSED_PATH = Path("data/processed/papers.json")
OUTPUT_PATH = Path("data/processed/similarity_results.json")

THRESHOLD = 0.35


def hf_similarity(source: str, targets: list, retries: int = 5) -> list | None:
    for i in range(retries):
        response = requests.post(URL, headers=HEADERS, json={
            "inputs": {
                "source_sentence": source[:512],
                "sentences": [t[:512] for t in targets]
            }
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
    papers = [p for p in papers if p["abstract"]]

    pairs = []
    similar = []

    total = len(papers)
    count = 0
    total_pairs = (total * (total - 1)) // 2
    print(f"Computing similarity for {total} papers ({total_pairs} pairs)...")

    for i in range(total):
        source = papers[i]
        targets = papers[i+1:]
        if not targets:
            continue

        scores = hf_similarity(source["abstract"], [t["abstract"] for t in targets])
        if not scores:
            continue

        for j, score in enumerate(scores):
            target = targets[j]
            count += 1
            pair = {
                "paper1": source["id"],
                "paper2": target["id"],
                "score": round(float(score), 4)
            }
            pairs.append(pair)
            if float(score) >= THRESHOLD:
                similar.append(pair)
                print(f"  SIMILAR ({score:.3f}): {source['title'][:30]} <-> {target['title'][:30]}")

        time.sleep(0.5)

    results = {
        "threshold": THRESHOLD,
        "total_pairs": count,
        "similar_pairs": len(similar),
        "pairs": pairs,
        "similar": similar
    }

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nDone. {len(similar)} similar pairs found out of {count}.")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
