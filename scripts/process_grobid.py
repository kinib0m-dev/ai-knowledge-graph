import os
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

GROBID_URL = os.environ.get("GROBID_URL", "http://localhost:8070")
PAPERS_DIR = Path("data/papers")
GROBID_OUTPUT_DIR = Path("data/grobid_output")
PROCESSED_DIR = Path("data/processed")

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def process_pdf(pdf_path: Path) -> Path | None:
    """Send a PDF to Grobid and save the TEI XML response."""
    output_path = GROBID_OUTPUT_DIR / (pdf_path.stem + ".tei.xml")
    if output_path.exists():
        print(f"INFO: Skipping '{pdf_path.name}' — already processed.")
        return output_path

    with open(pdf_path, "rb") as f:
        response = requests.post(
            f"{GROBID_URL}/api/processFulltextDocument",
            files={"input": f},
            data={"consolidateHeader": "1"},
            timeout=120,
        )

    if response.status_code == 200:
        output_path.write_text(response.text, encoding="utf-8")
        print(f"INFO: Processed '{pdf_path.name}'")
        return output_path
    else:
        print(f"ERROR: Failed '{pdf_path.name}' — status {response.status_code}")
        return None


def extract_text(tei_path: Path) -> dict:
    """Extract title, abstract, acknowledgements and authors from TEI XML."""
    tree = ET.parse(tei_path)
    root = tree.getroot()

    # Title
    title_el = root.find(".//tei:titleStmt/tei:title", NS)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    # Abstract
    abstract_el = root.find(".//tei:abstract", NS)
    abstract = " ".join(abstract_el.itertext()).strip() if abstract_el is not None else ""

    # Authors
    authors = []
    for author in root.findall(".//tei:fileDesc//tei:author", NS):
        forename = author.find(".//tei:forename", NS)
        surname = author.find(".//tei:surname", NS)
        name_parts = [p.text for p in [forename, surname] if p is not None and p.text]
        if name_parts:
            authors.append(" ".join(name_parts))

    # Acknowledgements
    ack_el = root.find(".//tei:div[@type='acknowledgement']", NS)
    acknowledgements = " ".join(ack_el.itertext()).strip() if ack_el is not None else ""

    return {
        "id": tei_path.stem.replace(".tei", ""),
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "acknowledgements": acknowledgements,
    }


def main():
    GROBID_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(PAPERS_DIR.glob("*.pdf"))
    print(f"INFO: Found {len(pdfs)} PDFs.")

    papers = []
    for pdf in pdfs:
        tei_path = process_pdf(pdf)
        if tei_path:
            paper = extract_text(tei_path)
            papers.append(paper)
            print(f"  title: {paper['title'][:60]}")
            print(f"  authors: {len(paper['authors'])}")
            print(f"  abstract: {len(paper['abstract'])} chars")
            print(f"  acknowledgements: {len(paper['acknowledgements'])} chars")

    output_path = PROCESSED_DIR / "papers.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(papers)}/30 papers saved to '{output_path}'.")


if __name__ == "__main__":
    main()
