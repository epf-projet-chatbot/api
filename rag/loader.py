"""Document loading and chunking — adaptive by document type."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

_TYPE_RULES: list[tuple[list[str], str]] = [
    (["avenant"], "avenant"),
    (["convention"], "convention"),
    (["commande", "bdc", "bon-de-commande"], "bon_de_commande"),
    (["recette", "pv", "procès-verbal", "proces-verbal"], "proces_verbal"),
    (["scrapping", "veille", "changements-légaux", "cadre-legal"], "veille_juridique"),
    (["book", "comptab"], "comptabilite"),
    (["analyse", "litige"], "analyse"),
    (["knowledge", "base"], "base_de_connaissances"),
]

_CHUNK_SETTINGS: dict[str, tuple[int, int]] = {
    "avenant":              (700, 150),
    "convention":           (700, 150),
    "bon_de_commande":      (700, 150),
    "proces_verbal":        (600, 100),
    "veille_juridique":     (500,  80),
    "comptabilite":         (600, 100),
    "analyse":              (600, 100),
    "base_de_connaissances":(900, 150),
    "default":              (500, 100),
}


def _detect_type(name: str) -> str:
    lower = name.lower()
    for keywords, doc_type in _TYPE_RULES:
        if any(kw in lower for kw in keywords):
            return doc_type
    return "default"


def _get_splitter(doc_type: str) -> RecursiveCharacterTextSplitter:
    size, overlap = _CHUNK_SETTINGS.get(doc_type, _CHUNK_SETTINGS["default"])
    return RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " "],
    )


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    text = text.replace(" ", " ").replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove PDF artifacts: lone page numbers, repeated dashes
    text = re.sub(r"(?m)^\s*\d{1,3}\s*$", "", text)
    text = re.sub(r"-{4,}", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Loaders per file type
# ---------------------------------------------------------------------------

def _load_pdf(path: Path) -> list[Document]:
    try:
        return PyPDFLoader(str(path)).load()
    except Exception:
        return []


def _load_json_kb(path: Path) -> list[Document]:
    """Handle output.json knowledge base: [{filename, content}]."""
    try:
        items = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    if not isinstance(items, list):
        return [Document(page_content=json.dumps(items, ensure_ascii=False, indent=2),
                         metadata={"source": str(path), "doc_type": "json"})]
    docs = []
    for item in items:
        content = item.get("content", "")
        filename = item.get("filename", "")
        if content.strip():
            docs.append(Document(
                page_content=content,
                metadata={
                    "source": filename or str(path),
                    "doc_type": _detect_type(filename),
                    "page": 1,
                },
            ))
    return docs


def _load_markdown(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [Document(page_content=text, metadata={"source": str(path), "page": 1})]


def _load_file(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".json":
        return _load_json_kb(path)
    if suffix in (".md", ".txt"):
        return _load_markdown(path)
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _process_file(path: Path) -> list[Document]:
    """Load, clean, and chunk a single file."""
    raw_docs = _load_file(path)
    if not raw_docs:
        return []

    doc_type = _detect_type(path.name)
    output: list[Document] = []

    for doc in raw_docs:
        effective_type = doc.metadata.get("doc_type", doc_type)
        splitter = _get_splitter(effective_type)
        text = _clean(doc.page_content)
        for chunk in splitter.split_text(text):
            if len(chunk.strip()) < 30:
                continue
            output.append(Document(
                page_content=chunk,
                metadata={
                    "source": doc.metadata.get("source", str(path)),
                    "page": doc.metadata.get("page", 1),
                    "doc_type": effective_type,
                },
            ))
    return output


def process_documents(folder_path: str) -> list[Document]:
    """Load, clean, and chunk all documents in parallel with type-adaptive settings."""

    paths = [p for p in sorted(Path(folder_path).glob("**/*")) if p.is_file()]
    output: list[Document] = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_process_file, p): p for p in paths}
        for future in as_completed(futures):
            output.extend(future.result())

    return output
