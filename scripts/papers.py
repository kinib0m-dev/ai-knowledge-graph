import logging
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Papers from ArXiv
PAPERS = [
    # --- Original 10 (Deliverable 1) ---
    {"id": "1706.03762", "title": "Attention Is All You Need"},
    {"id": "1810.04805", "title": "BERT"},
    {"id": "2005.14165", "title": "GPT-3"},
    {"id": "1512.03385", "title": "Deep Residual Learning (ResNet)"},
    {"id": "1406.2661",  "title": "Generative Adversarial Networks"},
    {"id": "1412.6980",  "title": "Adam Optimizer"},
    {"id": "2103.00020", "title": "CLIP"},
    {"id": "2105.05233", "title": "Diffusion Models Beat GANs"},
    {"id": "2302.13971", "title": "LLaMA"},
    {"id": "1207.0580",  "title": "Dropout"},

    # --- LLMs / Transformers ---
    {"id": "2203.02155", "title": "InstructGPT (RLHF)"},
    {"id": "2208.01618", "title": "Whisper (Robust Speech Recognition)"},
    {"id": "2307.09288", "title": "LLaMA 2"},
    {"id": "2106.09685", "title": "LoRA"},
    {"id": "2204.05149", "title": "PaLM"},

    # --- Diffusion / Generative ---
    {"id": "2112.10752", "title": "Latent Diffusion Models (Stable Diffusion)"},
    {"id": "2006.11239", "title": "DDPM (Denoising Diffusion Probabilistic Models)"},
    {"id": "2112.01573", "title": "DALL-E 2 (Hierarchical Text-Conditional Image Generation)"},

    # --- Computer Vision ---
    {"id": "2010.11929", "title": "Vision Transformer (ViT)"},
    {"id": "1506.01497", "title": "Faster R-CNN"},
    {"id": "1505.04597", "title": "U-Net"},
    {"id": "2004.10934", "title": "YOLOv4"},

    # --- Reinforcement Learning ---
    {"id": "1312.5602",  "title": "Playing Atari with Deep Reinforcement Learning (DQN)"},
    {"id": "1707.06347", "title": "Proximal Policy Optimization (PPO)"},
    {"id": "2005.12729", "title": "Decision Transformer"},

    # --- Multimodal ---
    {"id": "2301.13688", "title": "BLIP-2"},
    {"id": "2309.17421", "title": "LLaVA"},

    # --- AI Ethics / Fairness ---
    {"id": "1803.09010", "title": "Fairness and Machine Learning"},
    {"id": "2109.13916", "title": "On the Opportunities and Risks of Foundation Models"},
    {"id": "2212.08073", "title": "Constitutional AI (Anthropic)"},
]

OUTPUT_DIR = Path("data/papers")
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}.pdf"


def download_paper(paper: dict, output_dir: Path) -> None:
    """Download a paper PDF from ArXiv."""
    arxiv_id = paper["id"]
    title = paper["title"]
    output_path = output_dir / f"{arxiv_id}.pdf"

    # No duplicate downloading
    if output_path.exists():
        logger.info(f"Skipping '{title}' — already downloaded.")
        return

    url = ARXIV_PDF_URL.format(id=arxiv_id)
    logger.info(f"Downloading '{title}' from {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Basic check, PDFs start with %PDF
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"Response for {arxiv_id} does not appear to be a PDF.")

        output_path.write_bytes(response.content)
        logger.info(f"Saved: {output_path}")

    except requests.RequestException as e:
        logger.error(f"Failed to download '{title}': {e}")
    except ValueError as e:
        logger.error(e)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for paper in PAPERS:
        download_paper(paper, OUTPUT_DIR)
        time.sleep(1)  # Avoid ratelimiting if any

    downloaded = list(OUTPUT_DIR.glob("*.pdf"))
    logger.info(f"\nDone. {len(downloaded)}/{len(PAPERS)} PDFs in '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
