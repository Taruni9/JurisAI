from backend.gemini_helper import llm
from vector_store.chroma_store import retrieve_documents


def answer_question(question, doc_id=None, user_id=None, cross_document=False):
    """
    Answer a question using retrieved context, and return the source
    location(s) the answer was grounded in so the UI can show
    "Page X, Paragraph Y" next to the answer.

    Returns: {"answer": str, "sources": [{"filename", "page", "paragraph"}]}
    """
    retrieved = retrieve_documents(
        question,
        doc_id=doc_id,
        user_id=user_id,
        cross_document=cross_document,
    )

    if not retrieved:
        return {
            "answer": "No relevant content was found in the document(s) to answer this question.",
            "sources": []
        }

    context_blocks = []
    for i, chunk in enumerate(retrieved, start=1):
        context_blocks.append(
            f"[Source {i} | {chunk['filename']} | Page {chunk['page']}, "
            f"Paragraph {chunk['paragraph']}]\n{chunk['text']}"
        )
    context = "\n\n".join(context_blocks)

    prompt = f"""
Answer the question using only the context below. The context is split into
numbered sources. Base your answer only on these sources.

Context:

{context}

Question:

{question}

Provide a clear, direct answer.
"""

    try:
        response = llm.invoke(prompt)
        answer_text = response.content
    except Exception as e:
        return {
            "answer": f"""
❌ Unable to answer the question.

Reason:

{str(e)}

Please wait for a minute and try again.
""",
            "sources": []
        }

    sources = [
        {
            "filename": chunk["filename"],
            "page": chunk["page"],
            "paragraph": chunk["paragraph"],
        }
        for chunk in retrieved
    ]

    return {"answer": answer_text, "sources": sources}
