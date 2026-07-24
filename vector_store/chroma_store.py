"""
Persistent, multi-document vector store built on ChromaDB.

Replaces the old in-memory FAISS store. Data is written to disk under
./chroma_data so documents remain searchable across app restarts and
sessions, and a single collection holds chunks from every uploaded
document (tagged with doc_id/user_id) so we can search across many
contracts at once.
"""

import os
import uuid

import chromadb
from embeddings.embedding_model import embedding_model

_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
os.makedirs(_PERSIST_DIR, exist_ok=True)

_client = chromadb.PersistentClient(path=_PERSIST_DIR)
_collection = _client.get_or_create_collection(name="jurisai_documents")


def add_documents(doc_id, filename, user_id, chunks):
    """
    Add chunks for one document to the persistent store.

    chunks: list of {"text": str, "page": int, "paragraph": int}
            (as produced by rag.chunker.chunk_structured_document)
    """
    if not chunks:
        return

    texts = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts).tolist()

    ids = [f"{doc_id}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "user_id": str(user_id),
            "page": c.get("page", 1),
            "paragraph": c.get("paragraph", 1),
        }
        for c in chunks
    ]

    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )


def retrieve_documents(question, doc_id=None, user_id=None, k=5, cross_document=False):
    """
    Retrieve the most relevant chunks for a question.

    - doc_id: restrict search to a single document (normal "chat with this
      contract" mode).
    - cross_document=True with user_id set: search across every document
      belonging to that user (multi-document search).

    Returns a list of dicts: {"text", "filename", "page", "paragraph"}
    """
    where = None
    if cross_document and user_id is not None:
        where = {"user_id": str(user_id)}
    elif doc_id is not None:
        where = {"doc_id": doc_id}

    question_embedding = embedding_model.encode([question]).tolist()

    try:
        results = _collection.query(
            query_embeddings=question_embedding,
            n_results=k,
            where=where,
        )
    except Exception:
        return []

    output = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for text, meta in zip(documents, metadatas):
        output.append({
            "text": text,
            "filename": meta.get("filename", "Unknown"),
            "page": meta.get("page", "?"),
            "paragraph": meta.get("paragraph", "?"),
        })

    return output


def delete_document(doc_id):
    """Remove all chunks belonging to a document (used by 'Clear Workspace')."""
    try:
        _collection.delete(where={"doc_id": doc_id})
    except Exception:
        pass
