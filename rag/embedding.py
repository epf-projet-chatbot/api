"""
It is now in the ingestion stack
"""

from __future__ import annotations

import os

try:
    from .config import get_embeddings
    from .ingest import delete_correction_from_chroma, get_all_corrections, ingest_folder
except ImportError:
    from rag.config import get_embeddings
    from rag.ingest import delete_correction_from_chroma, get_all_corrections, ingest_folder


def main() -> int:
    """CLI entrypoint kept for backward compatibility."""

    data_path = os.path.join(os.path.dirname(__file__), "data", "data_complete")
    return ingest_folder(data_path)


if __name__ == "__main__":
    raise SystemExit(main())
