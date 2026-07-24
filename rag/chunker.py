from langchain.text_splitter import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)


def chunk_document(text):
    """Backward-compatible plain-text chunker (no citation metadata)."""
    return _splitter.split_text(text)


def chunk_structured_document(structured_doc):
    """
    Chunk a structured document (from file_extractor.extract_structured)
    while keeping track of which page/paragraph each chunk came from, so
    answers can later be traced back to a source.

    Returns a list of dicts:
        {"text": chunk_text, "page": page_num, "paragraph": paragraph_num}
    """
    chunks = []

    for page in structured_doc["pages"]:
        page_num = page["page"]

        for paragraph_num, paragraph_text in enumerate(page["paragraphs"], start=1):
            if not paragraph_text.strip():
                continue

            if len(paragraph_text) <= 1000:
                pieces = [paragraph_text]
            else:
                pieces = _splitter.split_text(paragraph_text)

            for piece in pieces:
                chunks.append({
                    "text": piece,
                    "page": page_num,
                    "paragraph": paragraph_num
                })

    return chunks
