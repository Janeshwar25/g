"""agent.knowledge_base_indexer

Backend knowledge-base indexing.

On startup, the app can:
- scan `knowledge_base/`
- load supported docs (pdf/csv/xlsx/md/txt)
- chunk
- embed
- upsert into the persistent FAISS vector store

Rebuild policy:
- only reindex when KB file list or mtimes change (manifest-based)

This keeps end-user UI upload/index out of the main flow.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import Config

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".pdf", ".csv", ".xls", ".xlsx", ".md", ".txt"}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_fingerprint(path: str) -> str:
    """Stable-enough fingerprint: path + size + mtime."""
    st = os.stat(path)
    return f"{path}|{st.st_size}|{int(st.st_mtime)}"


def _scan_kb(kb_dir: str) -> List[str]:
    if not os.path.isdir(kb_dir):
        return []
    files: List[str] = []
    for root, _, filenames in os.walk(kb_dir):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SUPPORTED_EXTS:
                files.append(os.path.join(root, fn))
    return sorted(files)


def _load_manifest(path: str) -> Dict[str, str]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception as e:
        logger.warning("KB manifest read failed: %s", e)
    return {}


def _save_manifest(path: str, manifest: Dict[str, str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


@dataclass
class KBIndexResult:
    indexed_files: int
    indexed_chunks: int
    skipped_files: int
    vector_store_path: str
    manifest_path: str


def ensure_knowledge_base_index(
    config: Optional[Config] = None,
    kb_dir: str = "knowledge_base",
    manifest_path: str = "vector_store_db/kb_manifest.json",
) -> KBIndexResult:
    """Idempotently ensure KB docs are indexed into the FAISS store."""

    cfg = config or Config()

    kb_files = _scan_kb(kb_dir)
    current_manifest = {p: _file_fingerprint(p) for p in kb_files}

    prior_manifest = _load_manifest(manifest_path)

    # If identical fingerprints, do nothing
    if current_manifest and prior_manifest == current_manifest and os.path.exists("vector_store_db"):
        logger.info("[KB] Knowledge base unchanged; using existing vector store")
        return KBIndexResult(
            indexed_files=0,
            indexed_chunks=0,
            skipped_files=len(kb_files),
            vector_store_path="vector_store_db",
            manifest_path=manifest_path,
        )

    if not kb_files:
        logger.warning("[KB] No supported files found in %s", kb_dir)
        _save_manifest(manifest_path, current_manifest)
        return KBIndexResult(
            indexed_files=0,
            indexed_chunks=0,
            skipped_files=0,
            vector_store_path="vector_store_db",
            manifest_path=manifest_path,
        )

    # Rebuild index from scratch for correctness and simplicity
    logger.info("[KB] (Re)indexing knowledge base: %d files", len(kb_files))

    try:
        # Local imports to avoid import cost if unchanged
        from agent.document_loader import load_document
        from agent.chunker import chunk_documents
        from agent.vector_store import add_documents_to_store

        # Remove existing store to avoid duplicates
        if os.path.isdir("vector_store_db"):
            # keep directory removal simple
            import shutil

            shutil.rmtree("vector_store_db", ignore_errors=True)

        all_chunks = []
        indexed_files = 0

        for path in kb_files:
            original_filename = os.path.basename(path)
            docs = load_document(path, original_filename)
            if not docs:
                continue
            chunks = chunk_documents(docs)
            if chunks:
                all_chunks.extend(chunks)
            indexed_files += 1

        ok = add_documents_to_store(all_chunks, cfg)
        if not ok:
            raise RuntimeError("Failed to write vector store")

        _save_manifest(manifest_path, current_manifest)
        logger.info("[KB] Indexed files=%d chunks=%d", indexed_files, len(all_chunks))
        return KBIndexResult(
            indexed_files=indexed_files,
            indexed_chunks=len(all_chunks),
            skipped_files=0,
            vector_store_path="vector_store_db",
            manifest_path=manifest_path,
        )

    except Exception as e:
        logger.exception("[KB] Indexing failed: %s", e)
        # Do not crash the app; keep manifest update so we can retry later
        _save_manifest(manifest_path, prior_manifest)
        return KBIndexResult(
            indexed_files=0,
            indexed_chunks=0,
            skipped_files=0,
            vector_store_path="vector_store_db",
            manifest_path=manifest_path,
        )
