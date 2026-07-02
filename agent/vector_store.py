"""
Vector Store mapping for Enterprise RAG.
Manages the FAISS index.
"""
import logging
import os
from typing import List, Optional
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from agent.embedding_service import get_embedding_model
from config import Config

logger = logging.getLogger(__name__)

VECTOR_STORE_PATH = "vector_store_db"

def get_vector_store(config: Optional[Config] = None) -> Optional[FAISS]:
    """Loads existing vector store if it exists."""
    config = config or Config()
    if os.path.exists(VECTOR_STORE_PATH):
        try:
            embeddings = get_embedding_model(config)
            return FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            logger.error("Failed to load vector store: %s", e)
            return None
    return None

def add_documents_to_store(documents: List[Document], config: Optional[Config] = None) -> bool:
    """Adds chunks to the FAISS vector store and saves to disk."""
    if not documents:
        return False
        
    config = config or Config()
    embeddings = get_embedding_model(config)
    
    try:
        vs = get_vector_store(config)
        if vs:
            vs.add_documents(documents)
            vs.save_local(VECTOR_STORE_PATH)
            logger.info("Added %d chunks to existing vector store", len(documents))
        else:
            vs = FAISS.from_documents(documents, embeddings)
            vs.save_local(VECTOR_STORE_PATH)
            logger.info("Created new vector store with %d chunks", len(documents))
        return True
    except Exception as e:
        logger.error("Error adding documents to vs: %s", e, exc_info=True)
        return False
