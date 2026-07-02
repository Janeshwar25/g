import logging
from typing import Optional, List
import requests
from langchain_core.embeddings import Embeddings
from config import Config
from agent.enterprise_llm import EnterpriseLLMClient

logger = logging.getLogger(__name__)

class EnterpriseEmbeddingClient(Embeddings):
    """Enterprise embedding client using Azure OpenAI Gateway."""
    
    def __init__(self, config: Config):
        self.llm_client = EnterpriseLLMClient(config)
        
        # 1 & 5. Use dedicated embedding configuration, not chat configuration
        base_url = getattr(config, "LLM_EMBEDDING_BASE_URL", "https://api.uhg.com/api/cloud/api-management/ai-gateway/1.0").rstrip("/")
        self.deployment_name = getattr(config, "LLM_EMBEDDING_DEPLOYMENT_NAME", "azure/gpt-5.4_2026-03-05")
        self.model_name = getattr(config, "LLM_EMBEDDING_MODEL_NAME", "azure/gpt-5.4_2026-03-05")
        api_version = getattr(config, "LLM_EMBEDDING_API_VERSION", "2026-03-05")
        
        # Construct endpoint
        self.endpoint = f"{base_url}/openai/deployments/{self.deployment_name}/embeddings?api-version={api_version}"
        self.project_id = self.llm_client.project_id

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        # 2. Call the public get_access_token method
        token = self.llm_client.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "projectId": self.project_id,
            self.llm_client.project_header: self.project_id
        }
        
        # 4. Support batch embeddings natively in the payload
        payload = {
            "model": self.model_name,
            "input": texts
        }
        
        try:
            response = requests.post(
                self.endpoint, 
                json=payload, 
                headers=headers, 
                timeout=120, 
                verify=self.llm_client.verify_ssl
            )
        except Exception as e:
            # Catch network/connection errors
            raise RuntimeError(f"Embedding request failed due to connection error: {e}")
            
        # 3. Improve error handling
        if not response.ok:
            logger.error("Embedding API Error!")
            logger.error("URL: %s", self.endpoint)
            logger.error("HTTP Status: %d", response.status_code)
            logger.error("Deployment Name: %s", self.deployment_name)
            logger.error("Model Name: %s", self.model_name)
            logger.error("Response Body: %s", response.text)
            raise RuntimeError(f"Embedding API returned HTTP {response.status_code}. See logs for details.")

        try:
            data = response.json()
        except Exception as e:
            logger.error("Failed to parse JSON response: %s", response.text)
            raise RuntimeError("Embedding API returned invalid JSON.")

        # 6. Robust response validation
        if "data" not in data:
            logger.error("Response missing 'data' field: %s", data)
            raise RuntimeError("Embedding API response missing 'data' field.")
            
        if not isinstance(data["data"], list):
            logger.error("'data' field is not a list: %s", data)
            raise RuntimeError("Embedding API response 'data' field must be a list.")
            
        if len(data["data"]) == 0:
            logger.error("'data' list is empty: %s", data)
            raise RuntimeError("Embedding API response returned empty 'data' list.")
            
        if "embedding" not in data["data"][0]:
            logger.error("First item in 'data' missing 'embedding' field: %s", data)
            raise RuntimeError("Embedding API response missing 'embedding' field.")

        # Parse all embeddings in order
        # Azure returns data as [{"index": 0, "embedding": [...]}, {"index": 1, "embedding": [...]}]
        # We ensure they are sorted by index to match the input texts
        sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in sorted_data]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # 4. Use batching for multiple documents
        if not texts:
            return []
        # Azure OpenAI typically has a max chunk limit (e.g. 16 or 100). We can chunk if needed.
        # For this refactor, we just pass the full list.
        return self._embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed_batch([text])[0]

def get_embedding_model(config: Optional[Config] = None) -> Embeddings:
    # 8. Preserve compatibility (returns Embeddings interface)
    """Returns the configured embedding model."""
    config = config or Config()

    logger.info("Initializing Enterprise Azure OpenAI Embeddings")
    return EnterpriseEmbeddingClient(config)
