import os
import json
import requests
import time
from pathlib import Path

HF_TOKEN = os.environ.get("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}
GOLD_PATH = Path("data/gold_standard.json")
PROCESSED_PATH = Path("data/processed/papers.json")

# --- Models to evaluate ---
NER_MODELS = [
    "dslim/bert-base-NER",
    "Jean-Baptiste/roberta-large-ner-english",
]

TOPIC_MODELS = [
    "facebook/bart-large-mnli",
    "typeform/distilbert-base-uncased-mnli",
]

SIMILARITY_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
]

SIMILARITY_THRESHOLD = 0.5

TOPIC_LABELS = [
    "Generative Models",
    "Language Models",
    "Computer Vision",
    "Reinforcement Learning",
    "AI Safety & Ethics",
    "Optimization & Training",
]


def hf_post(model: str, payload: dict, retries: int = 5) -> dict | None:
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    for i in range(retries):
        response = requests.post(url, headers=HEADERS, json=payload)
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


# --- NER Evaluation ---
def evaluate_ner(model: str, gold_papers: list, papers_by_id: dict) -> dict:
    print(f"\n  Evaluating NER: {model}")
    tp, fp, fn = 0, 0, 0

    for g in gold_papers:
        paper = papers_by_id.get(g["id"])
        if not paper or not paper["acknowledgements"]:
            continue

        result = hf_post(model, {"inputs": paper["acknowledgements"][:512]})
        if not result:
            continue

        # Flatten predicted entity strings
        predicted = set()
        if isinstance(result, list):
            for item in result:
                if isinstance(item, list):
                    for ent in item:
                        if ent.get("entity_group") in ("PER", "ORG"):
                            predicted.add(ent.get("word", "").strip())
                elif isinstance(item, dict):
                    if item.get("entity_group") in ("PER", "ORG"):
                        predicted.add(item.get("word", "").strip())

        gold_entities = set(
            g["entities"]["PER"] + g["entities"]["ORG"]
        )

        tp += len(predicted & gold_entities)
        fp += len(predicted - gold_entities)
        fn += len(gold_entities - predicted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {"model": model, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


# --- Topic Evaluation ---
def evaluate_topics(model: str, gold_papers: list, papers_by_id: dict) -> dict:
    print(f"\n  Evaluating Topics: {model}")
    correct = 0
    total = 0

    for g in gold_papers:
        paper = papers_by_id.get(g["id"])
        if not paper or not paper["abstract"]:
            continue

        result = hf_post(model, {
            "inputs": paper["abstract"][:512],
            "parameters": {"candidate_labels": TOPIC_LABELS}
        })
        if not result:
            continue

        if isinstance(result, list):
            result = result[0]

        # Handle both old and new API response formats
        if "labels" in result:
            predicted = result["labels"][0]
        elif "label" in result:
            predicted = result["label"]
        else:
            print(f"  Unexpected result format: {result}")
            continue

        if predicted == g["topic"]:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0
    return {"model": model, "accuracy": round(accuracy, 3), "correct": correct, "total": total}


# --- Similarity Evaluation ---
def evaluate_similarity(model: str, gold_papers: list, papers_by_id: dict) -> dict:
    print(f"\n  Evaluating Similarity: {model}")
    tp, fp, fn, tn = 0, 0, 0, 0

    ids = [g["id"] for g in gold_papers]
    gold_similar = set()
    for g in gold_papers:
        for sim_id in g["similar_to"]:
            if sim_id in ids:
                pair = tuple(sorted([g["id"], sim_id]))
                gold_similar.add(pair)

    for i, id1 in enumerate(ids):
        for id2 in ids[i+1:]:
            p1 = papers_by_id.get(id1)
            p2 = papers_by_id.get(id2)
            if not p1 or not p2:
                continue
            if not p1["abstract"] or not p2["abstract"]:
                continue

            result = hf_post(model, {
                "inputs": {
                    "source_sentence": p1["abstract"][:512],
                    "sentences": [p2["abstract"][:512]]
                }
            })
            if not result or not isinstance(result, list):
                continue

            score = result[0] if isinstance(result[0], float) else 0.0
            pair = tuple(sorted([id1, id2]))
            predicted_similar = score >= SIMILARITY_THRESHOLD

            if predicted_similar and pair in gold_similar:
                tp += 1
            elif predicted_similar and pair not in gold_similar:
                fp += 1
            elif not predicted_similar and pair in gold_similar:
                fn += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {"model": model, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def main():
    gold = json.loads(GOLD_PATH.read_text())
    papers = json.loads(PROCESSED_PATH.read_text())
    papers_by_id = {p["id"]: p for p in papers}

    results = {"ner": [], "topic": [], "similarity": []}

    print("=== NER Evaluation ===")
    for model in NER_MODELS:
        results["ner"].append(evaluate_ner(model, gold, papers_by_id))

    print("\n=== Topic Evaluation ===")
    for model in TOPIC_MODELS:
        results["topic"].append(evaluate_topics(model, gold, papers_by_id))

    print("\n=== Similarity Evaluation ===")
    for model in SIMILARITY_MODELS:
        results["similarity"].append(evaluate_similarity(model, gold, papers_by_id))

    out = Path("data/processed/model_evaluation.json")
    out.write_text(json.dumps(results, indent=2))

    print("\n\n=== RESULTS ===")
    print("\nNER:")
    for r in results["ner"]:
        print(f"  {r['model']}: P={r['precision']} R={r['recall']} F1={r['f1']}")
    print("\nTopic:")
    for r in results["topic"]:
        print(f"  {r['model']}: Accuracy={r['accuracy']} ({r['correct']}/{r['total']})")
    print("\nSimilarity:")
    for r in results["similarity"]:
        print(f"  {r['model']}: P={r['precision']} R={r['recall']} F1={r['f1']}")

    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
