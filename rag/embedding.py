from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from copy import deepcopy
from typing import Iterable, List, Tuple

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from loader import process_documents

load_dotenv()

# ----------------------------
# Config
# ----------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(SCRIPT_DIR, "data", "data_complete")

CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(SCRIPT_DIR, "chroma_db"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b")

# Batch côté application (Chroma + Ollama peuvent être sensibles)
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))
MAX_BATCH_CHARS = int(os.getenv("EMBED_MAX_BATCH_CHARS", "12000"))

# Garde-fous (juridique => chunks parfois énormes)
EMBED_MAX_CHARS = int(os.getenv("EMBED_MAX_CHARS", "12000"))
EMBED_MIN_SPLIT_CHARS = int(os.getenv("EMBED_MIN_SPLIT_CHARS", "1200"))
MAX_SPLIT_DEPTH = int(os.getenv("EMBED_MAX_SPLIT_DEPTH", "8"))  # 2^8 = 256 sous-chunks max

# Retries soft (réseau/runner)
RETRY_SLEEP_SEC = float(os.getenv("EMBED_RETRY_SLEEP_SEC", "0.8"))
MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "2"))

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Nettoyage fort (évite 400 sur inputs bizarres)."""
    if not text:
        return ""
    t = text.replace("\x00", "")  # NUL bytes
    t = t.strip()
    t = _WHITESPACE_RE.sub(" ", t)
    return t


def stable_chunk_id(source: str, page: int, text: str) -> str:
    """
    ID stable basé sur (source, page, contenu nettoyé).
    Évite de dépendre de l'index i qui change au moindre re-split.
    """
    h = hashlib.sha1()
    h.update(source.encode("utf-8", errors="ignore"))
    h.update(b"\x1f")
    h.update(str(page).encode("utf-8"))
    h.update(b"\x1f")
    h.update(text.encode("utf-8", errors="ignore"))
    return f"{source}:{page}:{h.hexdigest()}"


def prepare_chunks(docs: List[Document]) -> Tuple[List[Document], List[str], dict]:
    """
    - Nettoie le texte
    - Ignore vides
    - Tronque au max
    - Génère des ids stables
    """
    prepared: List[Document] = []
    ids: List[str] = []

    stats = {
        "input_docs": len(docs),
        "kept": 0,
        "skipped_empty": 0,
        "truncated": 0,
    }

    for d in docs:
        source = d.metadata.get("source", "unknown")
        page = int(d.metadata.get("page", 0))

        t = normalize_text(d.page_content or "")
        if not t:
            stats["skipped_empty"] += 1
            continue

        if len(t) > EMBED_MAX_CHARS:
            t = t[:EMBED_MAX_CHARS]
            stats["truncated"] += 1

        # Copie légère pour ne pas muter l'input
        nd = Document(page_content=t, metadata=deepcopy(d.metadata))
        cid = stable_chunk_id(source, page, t)
        nd.metadata["id"] = cid

        prepared.append(nd)
        ids.append(cid)

    stats["kept"] = len(prepared)
    return prepared, ids, stats


def split_in_two(doc: Document, doc_id: str) -> Tuple[List[Document], List[str]]:
    """Split simple en 2 (dichotomie) avec ids dérivés."""
    t = doc.page_content or ""
    mid = len(t) // 2
    left = normalize_text(t[:mid])
    right = normalize_text(t[mid:])

    out_docs: List[Document] = []
    out_ids: List[str] = []

    if left:
        d1 = Document(page_content=left, metadata=deepcopy(doc.metadata))
        d1.metadata["id"] = f"{doc_id}::a"
        out_docs.append(d1)
        out_ids.append(d1.metadata["id"])
    if right:
        d2 = Document(page_content=right, metadata=deepcopy(doc.metadata))
        d2.metadata["id"] = f"{doc_id}::b"
        out_docs.append(d2)
        out_ids.append(d2.metadata["id"])

    return out_docs, out_ids


def is_bad_request(err: Exception) -> bool:
    m = str(err).lower()
    return ("status code: 400" in m) or (" eof" in m) or ("do embedding request" in m)


def is_transient(err: Exception) -> bool:
    m = str(err).lower()
    return (
        "runner process has terminated" in m
        or "status code: 500" in m
        or "signal: killed" in m
        or "connection reset" in m
        or "timeout" in m
    )


def add_to_chroma(docs: List[Document]) -> bool:
    print(f"Initialisation Ollama embeddings: {OLLAMA_EMBED_MODEL} ({OLLAMA_BASE_URL})")
    embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    print(f"Modèle d'embedding prêt : {OLLAMA_EMBED_MODEL}")

    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    chunks, ids, stats = prepare_chunks(docs)
    print(
        f"Préparation chunks: input={stats['input_docs']} kept={stats['kept']} "
        f"skipped_empty={stats['skipped_empty']} truncated={stats['truncated']} "
        f"max_chars={EMBED_MAX_CHARS}"
    )

    if not chunks:
        print("Aucun chunk valide à indexer.")
        return True

    # Déduplication intra-run (évite re-ajout si split / collisions)
    seen = set()
    filtered_chunks, filtered_ids = [], []
    for c, cid in zip(chunks, ids):
        if cid in seen:
            continue
        seen.add(cid)
        filtered_chunks.append(c)
        filtered_ids.append(cid)
    chunks, ids = filtered_chunks, filtered_ids

    print(f"Indexation: {len(chunks)} chunks, batch_size={BATCH_SIZE}")

    index = 0
    split_count = 0
    skipped_count = 0

    while index < len(chunks):
        batch_chunks: List[Document] = []
        batch_ids: List[str] = []
        batch_chars = 0

        probe = index
        while probe < len(chunks) and len(batch_chunks) < BATCH_SIZE:
            candidate = chunks[probe]
            candidate_len = len(candidate.page_content or "")
            if batch_chunks and (batch_chars + candidate_len) > MAX_BATCH_CHARS:
                break
            batch_chunks.append(candidate)
            batch_ids.append(ids[probe])
            batch_chars += candidate_len
            probe += 1

        if not batch_chunks:
            # Fallback sécurité: toujours traiter au moins 1 chunk
            batch_chunks = [chunks[index]]
            batch_ids = [ids[index]]
            batch_chars = len(chunks[index].page_content or "")

        batch_start = index + 1
        batch_end = index + len(batch_chunks)
        start_time = time.perf_counter()
        print(
            f"[PROGRESS] Batch {batch_start}-{batch_end}/{len(chunks)} "
            f"items={len(batch_chunks)} chars={batch_chars}"
        )

        # retries transients (sans réduire batch ici; on est déjà prudent)
        attempt = 0
        while True:
            try:
                db.add_documents(batch_chunks, ids=batch_ids)
                break
            except Exception as e:
                attempt += 1
                if is_transient(e) and attempt <= MAX_RETRIES:
                    print(f"[WARN] Erreur transitoire (attempt {attempt}/{MAX_RETRIES}): {e}")
                    time.sleep(RETRY_SLEEP_SEC)
                    continue

                # Si batch>1 et ça casse, on réduit à 1 pour isoler le coupable
                if len(batch_chunks) > 1:
                    # remplace ce batch par des batches unitaires
                    chunks[index : index + len(batch_chunks)] = batch_chunks
                    ids[index : index + len(batch_ids)] = batch_ids
                    # force traitement unitaire en baissant BATCH_SIZE localement
                    # (sans toucher la config globale)
                    print("[WARN] Batch failed -> fallback en traitement unitaire pour isoler le chunk.")
                    # On traite le premier item en solo tout de suite
                    batch_chunks = [chunks[index]]
                    batch_ids = [ids[index]]
                    attempt = 0
                    continue

                # Ici batch=1 : on log et on tente split si BAD REQUEST
                bad_doc = batch_chunks[0]
                bad_id = batch_ids[0]
                txt = bad_doc.page_content or ""
                print("---- EMBEDDING FAILED ----")
                print(f"id={bad_id}")
                print(f"len_chars={len(txt)}")
                print(f"start={repr(txt[:200])}")
                print(f"end={repr(txt[-200:])}")
                print(f"error={e}")
                print("--------------------------")

                if is_bad_request(e) and len(txt) >= EMBED_MIN_SPLIT_CHARS:
                    # Split dichotomique, limité en profondeur
                    depth = int(bad_doc.metadata.get("_split_depth", 0))
                    if depth < MAX_SPLIT_DEPTH:
                        new_docs, new_ids = split_in_two(bad_doc, bad_id)
                        if new_docs:
                            for nd in new_docs:
                                nd.metadata["_split_depth"] = depth + 1
                            chunks[index : index + 1] = new_docs
                            ids[index : index + 1] = new_ids
                            split_count += 1
                            print(f"[INFO] Chunk scindé (depth {depth+1}) en {len(new_docs)} sous-chunks. Retry...")
                            attempt = 0
                            continue

                # Sinon on skip ce chunk et on continue
                skipped_count += 1
                print(f"[WARN] Chunk ignoré (id={bad_id}).")
                index += 1
                break

        # succès batch
        elapsed = time.perf_counter() - start_time
        print(f"[OK] Ajouté: {len(batch_chunks)} chunks en {elapsed:.2f}s")
        index += len(batch_chunks)

    print(f"Terminé. split_count={split_count} skipped_count={skipped_count}")
    return True


def main() -> int:
    data_path = os.getenv("DATA_PATH", DEFAULT_DATA_PATH)
    if not os.path.exists(data_path):
        print(f"Erreur : Le répertoire {data_path} n'existe pas.", file=sys.stderr)
        return 2

    docs = process_documents(data_path)
    if not docs:
        print("Aucun document trouvé à traiter.")
        return 0

    ok = add_to_chroma(docs)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
