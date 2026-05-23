# modules/document_store.py
# ─────────────────────────────────────────────────────────────────────────────
# Document Management — CRUD, embedding pipeline, and semantic search.
#
# Tables used:
#   document_types    — taxonomy (read-only after migration)
#   meeting_documents — one row per document uploaded
#   document_chunks   — chunked + embedded text for pgvector search
#
# All Supabase calls are fail-open (return None/False/[] on error).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _db():
    from modules.supabase_client import get_supabase_client
    return get_supabase_client()


# ── Taxonomy ──────────────────────────────────────────────────────────────────

def get_document_types() -> list[dict]:
    """Return all document taxonomy rows ordered by category + sort_order."""
    try:
        db = _db()
        if not db:
            return []
        return (
            db.table("document_types")
            .select("*")
            .order("category")
            .order("sort_order")
            .execute().data or []
        )
    except Exception:
        return []


def get_types_by_category() -> dict[str, list[dict]]:
    """Return taxonomy grouped by category. Useful for UI option-groups."""
    types = get_document_types()
    result: dict[str, list[dict]] = {}
    for t in types:
        result.setdefault(t["category"], []).append(t)
    return result


# ── meeting_documents CRUD ────────────────────────────────────────────────────

def upload_document(
    project_id: str,
    title: str,
    doc_type: str,
    content_text: str,
    file_name: str = "",
    meeting_id: Optional[str] = None,
    created_by: str = "",
    metadata: Optional[dict] = None,
    doc_date: Optional[str] = None,
    doc_date_estimated: Optional[str] = None,
) -> Optional[str]:
    """Insert a document record. Returns the new UUID or None on failure."""
    try:
        db = _db()
        if not db:
            return None
        row: dict = {
            "project_id":   project_id,
            "title":        title,
            "doc_type":     doc_type,
            "content_text": content_text,
            "file_name":    file_name,
            "created_by":   created_by,
            "metadata":     metadata or {},
        }
        if meeting_id:
            row["meeting_id"] = meeting_id
        if doc_date:
            row["doc_date"] = doc_date
        if doc_date_estimated:
            row["doc_date_estimated"] = doc_date_estimated.strip()
        result = db.table("meeting_documents").insert(row).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        logger.error("upload_document error: %s", exc)
        return None


def get_document(doc_id: str) -> Optional[dict]:
    """Return the full document row or None."""
    try:
        db = _db()
        if not db:
            return None
        rows = (
            db.table("meeting_documents")
            .select("*")
            .eq("id", doc_id)
            .limit(1)
            .execute().data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def get_document_content(doc_id: str) -> Optional[str]:
    """Return only the content_text of a document."""
    doc = get_document(doc_id)
    return doc["content_text"] if doc else None


def list_documents(
    project_id: str,
    meeting_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """List documents for a project; optionally filter by meeting or type."""
    try:
        db = _db()
        if not db:
            return []
        q = (
            db.table("meeting_documents")
            .select("id, project_id, meeting_id, title, doc_type, file_name, created_by, created_at, updated_at, metadata, doc_date, doc_date_estimated")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if meeting_id:
            q = q.eq("meeting_id", meeting_id)
        if doc_type:
            q = q.eq("doc_type", doc_type)
        return q.execute().data or []
    except Exception:
        return []


def update_document_meta(
    doc_id: str,
    title: Optional[str] = None,
    doc_type: Optional[str] = None,
    meeting_id: Optional[str] = None,
    doc_date: Optional[str] = None,
    doc_date_estimated: Optional[str] = None,
) -> bool:
    """Patch mutable fields of a document record."""
    try:
        db = _db()
        if not db:
            return False
        patch: dict = {}
        if title is not None:
            patch["title"] = title
        if doc_type is not None:
            patch["doc_type"] = doc_type
        if meeting_id is not None:
            patch["meeting_id"] = meeting_id
        if doc_date is not None:
            patch["doc_date"] = doc_date or None   # empty string → NULL
        if doc_date_estimated is not None:
            patch["doc_date_estimated"] = doc_date_estimated.strip() or None
        if not patch:
            return True
        db.table("meeting_documents").update(patch).eq("id", doc_id).execute()
        return True
    except Exception:
        return False


def delete_document(doc_id: str) -> bool:
    """Delete document and all its chunks (ON DELETE CASCADE)."""
    try:
        db = _db()
        if not db:
            return False
        db.table("meeting_documents").delete().eq("id", doc_id).execute()
        return True
    except Exception:
        return False


# ── Embedding pipeline ────────────────────────────────────────────────────────

def embed_document(
    doc_id: str,
    content_text: str,
    api_key: str = "",
    provider: str = "",
) -> bool:
    """
    Chunk content_text, embed each chunk, store in document_chunks.
    Re-indexing: deletes existing chunks before inserting new ones.

    api_key / provider: quando não fornecidos, resolvidos via
    get_active_embedding_params() (lê st.session_state).
    """
    try:
        from modules.embeddings import chunk_text, embed_batch, get_active_embedding_params
        db = _db()
        if not db:
            return False

        if not api_key or not provider:
            provider, api_key = get_active_embedding_params()

        # Remove existing chunks for a clean re-index
        db.table("document_chunks").delete().eq("document_id", doc_id).execute()

        chunks = chunk_text(content_text, chunk_size=500, overlap=80)
        if not chunks:
            return False

        embeddings = embed_batch(chunks, api_key, provider)
        if not embeddings:
            return False

        rows = [
            {
                "document_id": doc_id,
                "chunk_index": i,
                "content":     chunk,
                "embedding":   emb,
            }
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
            if emb
        ]
        if rows:
            # Insert in batches of 50 to stay within Supabase request limits
            batch_size = 50
            for start in range(0, len(rows), batch_size):
                db.table("document_chunks").insert(rows[start:start + batch_size]).execute()
        return True
    except Exception as exc:
        logger.error("embed_document error: %s", exc)
        return False


def get_chunks_count(doc_id: str) -> int:
    """Return the number of embedded chunks for a document."""
    try:
        db = _db()
        if not db:
            return 0
        result = (
            db.table("document_chunks")
            .select("id", count="exact")
            .eq("document_id", doc_id)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


# ── Semantic search ───────────────────────────────────────────────────────────

def search_documents_semantic(
    query: str,
    project_id: str,
    limit: int = 5,
    threshold: float = 0.4,
    meeting_id: Optional[str] = None,
    api_key: str = "",
    provider: str = "",
) -> list[dict]:
    """
    Embed the query and run pgvector cosine similarity search over document_chunks.
    Returns rows with: id, document_id, chunk_index, content, similarity,
                       doc_title, doc_type, doc_file_name.

    api_key / provider: quando não fornecidos, resolvidos via
    get_active_embedding_params() (lê st.session_state).
    """
    try:
        from modules.embeddings import embed_text, get_active_embedding_params
        db = _db()
        if not db:
            return []
        if not api_key or not provider:
            provider, api_key = get_active_embedding_params()
        embedding = embed_text(query, api_key, provider)
        if not embedding:
            return []
        result = db.rpc(
            "match_document_chunks",
            {
                "query_embedding":  embedding,
                "match_project_id": project_id,
                "match_count":      limit,
                "match_threshold":  threshold,
            },
        ).execute()
        rows = result.data or []
        # Post-filter by meeting_id if requested (meeting_id not in the SQL function)
        if meeting_id:
            docs_in_meeting = {
                d["id"] for d in list_documents(project_id, meeting_id=meeting_id)
            }
            rows = [r for r in rows if r["document_id"] in docs_in_meeting]
        return rows
    except Exception as exc:
        logger.error("search_documents_semantic error: %s", exc)
        return []


def search_documents_keyword(
    query: str,
    project_id: str,
    limit: int = 20,
) -> list[dict]:
    """Full-text keyword search in document title + content (case-insensitive)."""
    try:
        db = _db()
        if not db:
            return []
        # Search in title
        by_title = (
            db.table("meeting_documents")
            .select("id, title, doc_type, file_name, created_at, meeting_id, doc_date, doc_date_estimated")
            .eq("project_id", project_id)
            .ilike("title", f"%{query}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute().data or []
        )
        # Search in content
        by_content = (
            db.table("meeting_documents")
            .select("id, title, doc_type, file_name, created_at, meeting_id, doc_date, doc_date_estimated")
            .eq("project_id", project_id)
            .ilike("content_text", f"%{query}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute().data or []
        )
        # Merge, deduplicate by id, preserve relevance order (title matches first)
        seen: set[str] = set()
        merged: list[dict] = []
        for row in by_title + by_content:
            if row["id"] not in seen:
                seen.add(row["id"])
                merged.append(row)
        return merged[:limit]
    except Exception:
        return []
