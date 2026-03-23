"""Document loading and legal-aware chunking utilities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


LEGAL_SECTION_PATTERN = re.compile(
    r"(?im)^(article\s+\d+|section\s+\d+|chapitre\s+\d+|titre\s+\d+|annexe\s+\w+|\d+\.\d+\s+.+)$"
)


def clean_text(text: str) -> str:
    """Light cleaning while preserving legal structure."""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _infer_doc_type(source: str) -> str:
    src = source.lower()
    if "avenant" in src:
        return "avenant"
    if "convention" in src:
        return "convention"
    if "commande" in src:
        return "bon_de_commande"
    if "recette" in src or "pv" in src:
        return "proces_verbal"
    return "reference"


def _infer_topic(content: str) -> str:
    lowered = content.lower()
    if "rupture" in lowered:
        return "rupture"
    if "pro bono" in lowered or "pro-bono" in lowered:
        return "pro_bono"
    if "tac" in lowered:
        return "tac"
    if "wefa" in lowered:
        return "wefa"
    return "general"


def _extract_section(text: str) -> str:
    for line in text.splitlines()[:8]:
        match = LEGAL_SECTION_PATTERN.match(line.strip())
        if match:
            return match.group(1)
    return ""


def _split_legal_sections(text: str) -> list[str]:
    """Prefer splitting by legal titles/articles before size-based splitting."""

    lines = text.splitlines()
    parts: list[list[str]] = [[]]
    for line in lines:
        if LEGAL_SECTION_PATTERN.match(line.strip()) and parts[-1]:
            parts.append([])
        parts[-1].append(line)

    sections = ["\n".join(part).strip() for part in parts if any(chunk.strip() for chunk in part)]
    return sections if sections else [text]


def _load_pdf(path: Path) -> list[Document]:
    loader = PyPDFLoader(str(path))
    return loader.load()


def _load_markdown(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [Document(page_content=text, metadata={"source": str(path), "page": 1})]


def _load_json(path: Path) -> list[Document]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return [Document(page_content=pretty, metadata={"source": str(path), "page": 1})]


def load_documents(folder_path: str) -> list[Document]:
    """Load PDF/MD/JSON documents from folder recursively."""

    docs: list[Document] = []
    for file_path in Path(folder_path).glob("**/*"):
        if not file_path.is_file():
            continue
        try:
            if file_path.suffix.lower() == ".pdf":
                docs.extend(_load_pdf(file_path))
            elif file_path.suffix.lower() == ".md":
                docs.extend(_load_markdown(file_path))
            elif file_path.suffix.lower() == ".json":
                docs.extend(_load_json(file_path))
        except Exception:
            continue
    return docs


def _split_large_sections(sections: Iterable[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks: list[str] = []
    for section in sections:
        chunks.extend(splitter.split_text(section))
    return chunks


def process_documents(folder_path: str, chunk_size: int = 500, chunk_overlap: int = 100, lemmatize: bool = False) -> list[Document]:
    """Load, clean, split and enrich documents for ingestion."""

    _ = lemmatize  # kept for backward compatibility, intentionally unused.

    loaded = load_documents(folder_path)
    if not loaded:
        return []

    output: list[Document] = []
    for doc in loaded:
        source = str(doc.metadata.get("source", "source inconnue"))
        page = doc.metadata.get("page", "?")
        base_text = clean_text(doc.page_content)
        sections = _split_legal_sections(base_text)
        chunks = _split_large_sections(sections, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        for chunk in chunks:
            if not chunk.strip():
                continue
            output.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": source,
                        "page": page,
                        "section": _extract_section(chunk),
                        "doc_type": _infer_doc_type(source),
                        "topic": _infer_topic(chunk),
                    },
                )
            )

    return output