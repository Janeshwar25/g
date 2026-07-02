import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='credentials.env')

class Config:
    """Configuration class to centralize all environment variables and settings"""
    
    # API Configuration
    AHA_API_KEY = os.getenv('AHA_API_KEY', '')
    ICARUS_API_KEY = os.getenv('ICARUS_API_KEY', '')
    ICARUS_USERNAME = os.getenv('ICARUS_USERNAME', '')
    ICARUS_PASSWORD = os.getenv('ICARUS_PASSWORD', '')
    RALLY_API_KEY = os.getenv('RALLY_API_KEY', os.getenv('RALLY_API_KEY_CHRIS', ''))
    SMARTSHEET_API_KEY = os.getenv('SMARTSHEET_API_KEY', '')
    ACCELQ_API_KEY = os.getenv('ACCELQ_API_KEY', '')
    
    # Service URLs
    RALLY_URL = os.getenv('RALLY_URL', 'https://rally1.rallydev.com/slm/webservice/v2.0')
    AHA_BASE_URL = os.getenv('AHA_BASE_URL', 'https://optum.aha.io/api/v1')
    SMARTSHEET_BASE_URL = os.getenv('SMARTSHEET_BASE_URL', 'https://api.smartsheet.com/2.0')
    ICARUS_BASE_URL = os.getenv('ICARUS_BASE_URL', 'https://insights.hcp.uhg.com/api/icarus/v1')
    
    # Application Configuration
    API_HOST = os.getenv('API_HOST', '127.0.0.1')
    API_PORT = int(os.getenv('API_PORT') or '8000')
    STREAMLIT_HOST = os.getenv('STREAMLIT_HOST', '0.0.0.0')
    STREAMLIT_PORT = int(os.getenv('STREAMLIT_PORT') or '8080')
    
    # Internal API URL (for Streamlit to call FastAPI)
    API_BASE_URL = os.getenv('API_BASE_URL', f'http://127.0.0.1:8000')
    
    # Workspace and Project Configuration
    RALLY_WORKSPACE = os.getenv('RALLY_WORKSPACE', 'UHG')
    RALLY_PROJECT = os.getenv('RALLY_PROJECT', 'Pioneers GenAI')
    SMARTSHEET_WORKSPACE_ID = os.getenv('SMARTSHEET_WORKSPACE_ID', '')
    
    # File paths
    METADATA_FILE = os.getenv('METADATA_FILE', 'documents/plan_metadata.json')
    TEMPLATE_FILE = os.getenv('TEMPLATE_FILE', 'documents/GNP_Template_v4.xlsx')
    
    # Default values
    DEFAULT_BDL = os.getenv('DEFAULT_BDL', 'Jason Merckling')
    DEFAULT_RDL = os.getenv('DEFAULT_RDL', 'Chris Capewell')
    DEFAULT_BUSINESS_OWNER = os.getenv('DEFAULT_BUSINESS_OWNER', 'Gina Milana')
    
    # UI Configuration
    BUTTON_COLOR = os.getenv('BUTTON_COLOR', '#001f3f')  # Navy blue
    
    # Request timeouts
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT') or '180')
    
    # SSL Configuration
    VERIFY_SSL = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', '')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', '')
    MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'project_plans')
    MONGODB_COLLECTION = os.getenv('MONGODB_COLLECTION', 'plan_metadata')

    # AI Help Bot settings
    HELP_BOT_MAX_CONTEXT_CHARS = int(os.getenv('HELP_BOT_MAX_CONTEXT_CHARS') or '28000')
    HELP_BOT_MAX_HISTORY_MESSAGES = int(os.getenv('HELP_BOT_MAX_HISTORY_MESSAGES') or '10')

    # Contact IT/DevOps to obtain credentials.
    #
    LLM_GATEWAY_CLIENT_ID = os.getenv('LLM_GATEWAY_CLIENT_ID', '')
    LLM_GATEWAY_CLIENT_SECRET = os.getenv('LLM_GATEWAY_CLIENT_SECRET', '')
    LLM_GATEWAY_PROJECT_ID = os.getenv('LLM_GATEWAY_PROJECT_ID', '')
    LLM_GATEWAY_TOKEN_URL = os.getenv('LLM_GATEWAY_TOKEN_URL', 'https://api.uhg.com/oauth2/token')
    LLM_GATEWAY_SCOPE = os.getenv('LLM_GATEWAY_SCOPE', 'https://api.uhg.com/.default')
    
    # Base URLs
    LLM_GATEWAY_BASE_URL = os.getenv('LLM_GATEWAY_BASE_URL', 'https://api.uhg.com/api/cloud/api-management/ai-gateway/1.0')
    LLM_GATEWAY_REASONING_BASE_URL = os.getenv('LLM_GATEWAY_REASONING_BASE_URL', 'https://api.uhg.com/api/cloud/api-management/ai-gateway-reasoning/1.0')
    
    # Model names
    LLM_GATEWAY_MODEL_NAME = os.getenv('LLM_GATEWAY_MODEL_NAME', 'azure/gpt-5.3-chat_2026-03-03')
    LLM_GATEWAY_REASONING_MODEL_NAME = os.getenv('LLM_GATEWAY_REASONING_MODEL_NAME', 'azure/gpt-5.4_2026-03-05')
    
    LLM_GATEWAY_API_VERSION = os.getenv('LLM_GATEWAY_API_VERSION', '2025-01-01-preview')
    
    LLM_GATEWAY_INFERENCE_PATH = os.getenv('LLM_GATEWAY_INFERENCE_PATH', 'chat/completions')
    LLM_GATEWAY_PAYLOAD_SCHEMA = os.getenv('LLM_GATEWAY_PAYLOAD_SCHEMA', 'chat_completions')
    LLM_GATEWAY_PROJECT_HEADER = os.getenv('LLM_GATEWAY_PROJECT_HEADER', 'X-Project-Id')
    LLM_GATEWAY_EXTRA_HEADERS = os.getenv('LLM_GATEWAY_EXTRA_HEADERS', '')
    LLM_GATEWAY_TRACE_REQUESTS = os.getenv('LLM_GATEWAY_TRACE_REQUESTS', 'true').lower() == 'true'
    
    # Embedding Settings
    LLM_EMBEDDING_BASE_URL = os.getenv('LLM_EMBEDDING_BASE_URL', 'https://api.uhg.com/api/cloud/api-management/ai-gateway/1.0')
    LLM_EMBEDDING_MODEL_NAME = os.getenv('LLM_EMBEDDING_MODEL_NAME', 'text-embedding-ada-002')
    LLM_EMBEDDING_DEPLOYMENT_NAME = os.getenv('LLM_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002_2')
    LLM_EMBEDDING_API_VERSION = os.getenv('LLM_EMBEDDING_API_VERSION', '2023-05-15')
    
    # Retrieval Settings
    RETRIEVER_TYPE = os.getenv('RETRIEVER_TYPE', 'bm25').lower()
    BM25_TOP_K = int(os.getenv('BM25_TOP_K', '5'))
    BM25_SCORE_THRESHOLD = float(os.getenv('BM25_SCORE_THRESHOLD', '2.0'))
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '150'))
    MAX_CONTEXT_CHARS = int(os.getenv('MAX_CONTEXT_CHARS', '80000'))
    
    ENABLE_QUERY_EXPANSION = str(os.getenv('ENABLE_QUERY_EXPANSION', 'true')).lower() == 'true'
    ENABLE_FILENAME_BOOST = str(os.getenv('ENABLE_FILENAME_BOOST', 'true')).lower() == 'true'
    ENABLE_SESSION_CACHE = str(os.getenv('ENABLE_SESSION_CACHE', 'true')).lower() == 'true'
    ENABLE_RETRIEVER_STATS = str(os.getenv('ENABLE_RETRIEVER_STATS', 'true')).lower() == 'true'
    SESSION_TIMEOUT_SECONDS = int(os.getenv('SESSION_TIMEOUT_SECONDS', '1800'))
    
    @classmethod
    def validate_required_env_vars(cls):
        """Validate that required environment variables are set"""
        required_vars = [
            ('AHA_API_KEY', cls.AHA_API_KEY),
            ('ICARUS_API_KEY', cls.ICARUS_API_KEY),
            ('SMARTSHEET_API_KEY', cls.SMARTSHEET_API_KEY),
            ('SMARTSHEET_WORKSPACE_ID', cls.SMARTSHEET_WORKSPACE_ID),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value or var_value.strip() == '':
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True
    
    @classmethod
    def get_rally_headers(cls):
        """Get Rally API headers"""
        return {
            'ZSESSIONID': cls.RALLY_API_KEY,
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def get_aha_headers(cls):
        """Get AHA API headers"""
        # Handle both formats: with and without 'Bearer ' prefix
        api_key = cls.AHA_API_KEY.strip().strip("'").strip('"')  # Remove any quotes
        
        if api_key.startswith('Bearer '):
            # If it already has Bearer, use as-is
            auth_header = api_key
        else:
            # If it doesn't have Bearer, add it
            auth_header = f'Bearer {api_key}'
        
        return {
            'Authorization': auth_header,
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def get_smartsheet_headers(cls):
        """Get Smartsheet API headers"""
        return {
            'Authorization': f'Bearer {cls.SMARTSHEET_API_KEY}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def get_icarus_headers(cls):
        """Get Icarus API headers"""
        return {
            'Authorization': f'Bearer {cls.ICARUS_API_KEY}',
            'Accept': 'application/json'
        }
