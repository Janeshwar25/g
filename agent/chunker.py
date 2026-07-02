"""
Chunker for Enterprise RAG.
Splits documents into smaller chunks for vectorization.
"""
import logging
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

def chunk_documents(documents: List[Document], chunk_size: int = 1500, chunk_overlap: int = 150) -> List[Document]:
    """Splits a list of documents into chunks."""
    logger.info("Splitting %d documents", len(documents))
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        chunks = text_splitter.split_documents(documents)
        logger.info("Created %d chunks", len(chunks))
        return chunks
    except Exception as e:
        logger.error("Error splitting documents: %s", e, exc_info=True)
        return []
