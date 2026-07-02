"""MongoDB helper module for managing plan metadata"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from config import Config
import logging

logger = logging.getLogger(__name__)

class MongoDBHelper:
    """Helper class to manage MongoDB connections and operations"""
    
    def __init__(self):
        self.config = Config()
        self.client = None
        self.db = None
        self.collection = None
        self._connect()
    
    def _connect(self):
        """Establish connection to MongoDB"""
        try:
            # Use URI directly if it's a full connection string (mongodb+srv:// or mongodb://)
            if self.config.MONGODB_URI.startswith('mongodb+srv://') or self.config.MONGODB_URI.startswith('mongodb://'):
                uri = self.config.MONGODB_URI
            # Otherwise, build connection string with authentication for local MongoDB
            elif self.config.MONGODB_USERNAME and self.config.MONGODB_PASSWORD:
                uri = f"mongodb://{self.config.MONGODB_USERNAME}:{self.config.MONGODB_PASSWORD}@{self.config.MONGODB_URI.replace('mongodb://', '')}?authSource=admin"
            else:
                uri = self.config.MONGODB_URI
            
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[self.config.MONGODB_DATABASE]
            self.collection = self.db[self.config.MONGODB_COLLECTION]
            
            logger.info(f"Successfully connected to MongoDB: {self.config.MONGODB_DATABASE}")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def save_plan_metadata(self, rally_theme, metadata):
        """
        Save or update plan metadata in MongoDB
        
        Args:
            rally_theme (str): Strategic theme identifier (used as document ID)
            metadata (dict): Plan metadata containing idea, name, tag, prj, etc.
        """
        try:
            result = self.collection.update_one(
                {"_id": rally_theme},  # Use rally_theme as unique identifier
                {"$set": metadata},
                upsert=True  # Create if doesn't exist
            )
            
            if result.upserted_id:
                logger.info(f"Created new plan metadata for theme: {rally_theme}")
            else:
                logger.info(f"Updated plan metadata for theme: {rally_theme}")
            
            return True
        except OperationFailure as e:
            logger.error(f"Failed to save plan metadata: {e}")
            return False
    
    def get_plan_metadata(self, rally_theme):
        """
        Retrieve plan metadata from MongoDB
        
        Args:
            rally_theme (str): Strategic theme identifier
            
        Returns:
            dict: Plan metadata or None if not found
        """
        try:
            result = self.collection.find_one({"_id": rally_theme})
            if result:
                # Remove MongoDB _id from returned dict
                result.pop('_id', None)
            return result
        except OperationFailure as e:
            logger.error(f"Failed to retrieve plan metadata: {e}")
            return None
    
    def get_plan_metadata_by_key(self, key):
        """
        Retrieve plan metadata by either strategic theme or AHA idea
        Searches by the provided key directly first, then by idea field
        
        Args:
            key (str): Strategic theme or AHA idea identifier
            
        Returns:
            tuple: (metadata dict or None, actual_key used) 
        """
        try:
            # First try to find by _id (primary key)
            result = self.collection.find_one({"_id": key})
            if result:
                result.pop('_id', None)
                return (result, key)
            
            # If not found, try to find by idea field (for plans created with theme='none')
            result = self.collection.find_one({"idea": key})
            if result:
                actual_key = result['_id']
                result.pop('_id', None)
                return (result, actual_key)
            
            return (None, None)
        except OperationFailure as e:
            logger.error(f"Failed to retrieve plan metadata: {e}")
            return (None, None)
    
    def migrate_plan_key(self, old_key, new_key):
        """
        Migrate a plan document from one key to another.
        Used when a strategic theme is discovered for a plan that was created without one.
        
        Args:
            old_key (str): Current document key (e.g., AHA idea)
            new_key (str): New document key (e.g., strategic theme)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the document with old key
            old_doc = self.collection.find_one({"_id": old_key})
            if not old_doc:
                logger.warning(f"No document found with key: {old_key}")
                return False
            
            # Update rally_theme in the document
            old_doc['rally_theme'] = new_key
            
            # Insert with new key
            new_doc = old_doc.copy()
            new_doc['_id'] = new_key
            self.collection.insert_one(new_doc)
            
            # Delete old document
            self.collection.delete_one({"_id": old_key})
            
            logger.info(f"Successfully migrated plan from {old_key} to {new_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to migrate plan key: {e}")
            return False
    
    def update_plan_metadata(self, rally_theme, updates):
        """
        Update specific fields in plan metadata
        
        Args:
            rally_theme (str): Strategic theme identifier
            updates (dict): Dictionary of fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {"_id": rally_theme},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated plan metadata for theme: {rally_theme}")
                return True
            return False
        except OperationFailure as e:
            logger.error(f"Failed to update plan metadata: {e}")
            return False
    
    def get_all_plans(self, active_only=False):
        """
        Retrieve all plan metadata from MongoDB
        
        Args:
            active_only (bool): If True, only return plans where active=True
        
        Returns:
            dict: Dictionary with rally_theme as keys and metadata as values
        """
        try:
            plans = {}
            query = {"active": True} if active_only else {}
            for doc in self.collection.find(query):
                theme = doc.pop('_id')
                plans[theme] = doc
            return plans
        except OperationFailure as e:
            logger.error(f"Failed to retrieve all plans: {e}")
            return {}
    
    def set_plan_active(self, rally_theme, active=True):
        """
        Set the active flag for a plan
        
        Args:
            rally_theme (str): Strategic theme identifier
            active (bool): Whether the plan is active
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_plan_metadata(rally_theme, {"active": active})
    
    def delete_plan_metadata(self, rally_theme):
        """
        Delete plan metadata from MongoDB
        
        Args:
            rally_theme (str): Strategic theme identifier
            
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            result = self.collection.delete_one({"_id": rally_theme})
            if result.deleted_count > 0:
                logger.info(f"Deleted plan metadata for theme: {rally_theme}")
                return True
            return False
        except OperationFailure as e:
            logger.error(f"Failed to delete plan metadata: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def log_query(self, query: str, response_summary: str, tool_calls: list = None, user: str = None):
        """
        Log user queries for analytics (safe version - no full content).
        Only logs metadata, not full project data to avoid content filters.
        
        Args:
            query (str): User's query text (sanitized)
            response_summary (str): Brief summary of response (not full content)
            tool_calls (list): List of tools used (names only)
            user (str): Optional username
        """
        try:
            from datetime import datetime
            
            # Sanitize query - remove potential sensitive content
            sanitized_query = query[:500]  # Limit length
            
            # Create log document with minimal info
            log_doc = {
                "timestamp": datetime.now().isoformat(),
                "query_length": len(query),
                "query_preview": sanitized_query[:100],  # Only first 100 chars
                "response_length": len(response_summary),
                "tools_used": [tool.split('(')[0] if isinstance(tool, str) else tool.get('name', 'unknown') for tool in (tool_calls or [])],
                "tool_count": len(tool_calls) if tool_calls else 0,
                "user": user or "anonymous"
            }
            
            # Store in separate collection
            query_logs = self.db['query_logs']
            query_logs.insert_one(log_doc)
            
        except Exception as e:
            # Don't fail the request if logging fails
            logger.warning(f"Failed to log query: {e}")
