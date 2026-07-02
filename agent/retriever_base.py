from abc import ABC, abstractmethod
from typing import List, Tuple

class BaseRetriever(ABC):
    """
    Abstract interface for document retrieval.
    Allows seamlessly swapping between BM25, FAISS, or other retrieval engines.
    """
    
    @abstractmethod
    def retrieve(self, query: str, session_id: str = None) -> Tuple[str, List[str]]:
        """
        Retrieve context for a given query.
        
        Args:
            query: The user's query string.
            session_id: Optional identifier for conversation session caching.
            
        Returns:
            A tuple containing:
            1. Formatted context string (concatenated chunk text).
            2. List of unique document names used as sources.
        """
        pass
