import os
import math
import re
import time
import logging
from typing import Dict, List, Tuple, Any, Set

from config import Config
from agent.retriever_base import BaseRetriever
from agent.document_loader import load_document
from agent.chunker import chunk_documents

logger = logging.getLogger(__name__)

# Basic English stopwords for BM25 optimization
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", 
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", 
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", 
    "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", 
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", 
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", 
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", 
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", 
    "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", 
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", 
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", 
    "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", 
    "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", 
    "yourselves"
}

SYNONYMS = {
    "pmat": ["project", "manager", "application", "template", "pmat"],
    "bdl": ["business", "development", "lead", "bdl"],
    "rdl": ["requirements", "development", "lead", "rdl"],
    "st": ["strategic", "theme", "st"],
    "faq": ["frequently", "asked", "questions", "faq"],
    "optics": ["financials", "ppm", "optics"],
    "rally": ["icarus", "rally"],
    "metric": ["metrics", "metric"],
    "metrics": ["metrics", "metric"],
    "script": ["scripts", "script"],
    "scripts": ["scripts", "script"],
    "assignment": ["assignments", "assignment"],
    "assignments": ["assignments", "assignment"],
    "population": ["populations", "population"],
    "populations": ["populations", "population"],
}

FOLLOW_UP_PRONOUNS = {"it", "they", "this", "that", "those", "these", "he", "she", "them"}

def _expand_query(text: str) -> List[str]:
    """Expands query handling camelCase, hyphens, and synonyms."""
    text = re.sub('([a-z0-9])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('-', ' ')
    
    base_tokens = tokenize(text)
    expanded = set()
    for token in base_tokens:
        expanded.add(token)
        base_word = token[:-1] if token.endswith('s') and len(token) > 3 else token
        
        if token in SYNONYMS:
            expanded.update(SYNONYMS[token])
        elif base_word in SYNONYMS:
            expanded.update(SYNONYMS[base_word])
            
    return list(expanded)

SUMMARY_SHEETS = {"metrics", "dashboard", "summary", "statistics", "report"}

def _analyze_query(query: str) -> str:
    """Classifies the query intent."""
    query_lower = query.lower()
    
    detailed_keywords = {"explain", "describe", "details", "why", "how to"}
    for kw in detailed_keywords:
        if re.search(r'\b' + kw + r'\b', query_lower):
            return "DETAILED"
            
    aggregate_keywords = {
        "how many", "count", "total", "summary", "statistics", "metrics",
        "passed", "failed", "deferred", "completed", "pending", "all",
        "list all", "percentage", "execution"
    }
    for kw in aggregate_keywords:
        if re.search(r'\b' + kw + r'\b', query_lower):
            return "AGGREGATE"
            
    return "NORMAL"

def tokenize(text: str) -> List[str]:
    """Tokenize text: lowercase, remove punctuation, filter stopwords."""
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]

class BM25Retriever(BaseRetriever):
    """
    Production-ready BM25 Retrieval Engine.
    Chunks documents, caches them in memory, and scores them natively.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Config = None, kb_dir: str = "knowledge_base"):
        if self._initialized:
            return
            
        self.config = config or Config()
        self.kb_dir = kb_dir
        
        self.top_k = self.config.BM25_TOP_K
        self.score_threshold = self.config.BM25_SCORE_THRESHOLD
        self.chunk_size = self.config.CHUNK_SIZE
        self.chunk_overlap = self.config.CHUNK_OVERLAP
        self.max_context_chars = self.config.MAX_CONTEXT_CHARS
        
        self.enable_expansion = self.config.ENABLE_QUERY_EXPANSION
        self.enable_filename_boost = self.config.ENABLE_FILENAME_BOOST
        self.enable_session_cache = self.config.ENABLE_SESSION_CACHE
        self.enable_stats = self.config.ENABLE_RETRIEVER_STATS
        self.session_timeout = self.config.SESSION_TIMEOUT_SECONDS
        
        self._supported_exts = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".xls", ".csv"}
        
        # Core data structures
        self._file_cache: Dict[str, Dict] = {}
        self._all_chunks: List[Dict] = []
        self._doc_freq: Dict[str, int] = {}
        
        self._session_cache: Dict[str, Dict] = {}
        self._last_refresh_time = 0.0
        
        # Operational Metrics
        self.metrics = {
            "total_requests": 0,
            "total_retrieval_latency": 0.0,
            "total_llm_latency": 0.0,
            "llm_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_chunks_retrieved": 0,
        }
        
        self._initialized = True
        logger.info("Initialized BM25Retriever for %s", self.kb_dir)

    def _get_fingerprint(self, path: str) -> Tuple[float, int]:
        st = os.stat(path)
        return st.st_mtime, st.st_size

    def _scan_files(self) -> List[str]:
        if not os.path.isdir(self.kb_dir):
            return []
        files = []
        for root, _, filenames in os.walk(self.kb_dir):
            for fn in filenames:
                if fn.startswith(".") or fn.startswith("~"):
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext in self._supported_exts:
                    files.append(os.path.join(root, fn))
        return sorted(files)

    def _remove_chunks(self, path: str):
        """Incrementally remove chunks for a deleted or modified file."""
        cached = self._file_cache.get(path)
        if not cached:
            return
            
        chunks_to_remove = cached["chunks"]
        
        # Remove from global list
        self._all_chunks = [c for c in self._all_chunks if c not in chunks_to_remove]
        
        # Decrement document frequencies
        for chunk in chunks_to_remove:
            unique_tokens = set(chunk["tokens"])
            for token in unique_tokens:
                if token in self._doc_freq:
                    self._doc_freq[token] -= 1
                    if self._doc_freq[token] <= 0:
                        del self._doc_freq[token]

    def _add_chunks(self, path: str, chunks: List[Dict]):
        """Incrementally add new chunks to global state."""
        self._all_chunks.extend(chunks)
        
        for chunk in chunks:
            unique_tokens = set(chunk["tokens"])
            for token in unique_tokens:
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1

    def _refresh_cache(self):
        current_files = self._scan_files()
        current_file_set = set(current_files)
        
        for cached_path in list(self._file_cache.keys()):
            if cached_path not in current_file_set:
                logger.info("Removing deleted file from cache: %s", cached_path)
                self._remove_chunks(cached_path)
                del self._file_cache[cached_path]

        for path in current_files:
            try:
                mtime, size = self._get_fingerprint(path)
                cached = self._file_cache.get(path)
                if not cached or cached["mtime"] != mtime or cached["size"] != size:
                    # Remove old version if it existed
                    if cached:
                        self._remove_chunks(path)
                        
                    original_filename = os.path.basename(path)
                    docs = load_document(path, original_filename)
                    if not docs:
                        continue
                    
                    chunks = []
                    # Filter out docs that shouldn't be re-chunked (like Excel which is pre-batched)
                    to_chunk = []
                    for doc in docs:
                        if doc.metadata.get("file_type") in ['.xls', '.xlsx', '.csv']:
                            chunks.append(doc)
                        else:
                            to_chunk.append(doc)
                            
                    if to_chunk:
                        chunks.extend(chunk_documents(to_chunk, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap))
                    
                    structured_chunks = []
                    for i, chunk in enumerate(chunks):
                        structured_chunks.append({
                            "filepath": path,
                            "filename": original_filename,
                            "filename_lower": original_filename.lower(),
                            "filename_no_ext": os.path.splitext(original_filename)[0].lower(),
                            "sheet_name": chunk.metadata.get("sheet_name"),
                            "row_start": chunk.metadata.get("row_start"),
                            "row_end": chunk.metadata.get("row_end"),
                            "chunk_id": i + 1,
                            "page": chunk.metadata.get("page", None),
                            "text": chunk.page_content,
                            "tokens": tokenize(chunk.page_content)
                        })
                    
                    self._file_cache[path] = {
                        "mtime": mtime,
                        "size": size,
                        "chunks": structured_chunks
                    }
                    self._add_chunks(path, structured_chunks)
                    logger.info("Loaded: %s | %d chunks", original_filename, len(structured_chunks))
            except Exception as e:
                logger.error("Failed to load or cache document %s: %s", path, e)
                
        self._last_refresh_time = time.time()
        self._cleanup_sessions()

    def _cleanup_sessions(self):
        """Evict stale session caches."""
        now = time.time()
        stale = [sid for sid, data in self._session_cache.items() if now - data["time"] > self.session_timeout]
        for sid in stale:
            del self._session_cache[sid]

    def record_llm_latency(self, latency: float):
        """Tracks LLM latency metric."""
        self.metrics["total_llm_latency"] += latency
        self.metrics["llm_requests"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics for the debugging endpoint."""
        if not self.enable_stats:
            return {"error": "Stats are disabled in configuration."}
            
        self._refresh_cache()
        total_docs = len(self._file_cache)
        total_chunks = len(self._all_chunks)
        avg_chunk_size = sum(len(c["text"]) for c in self._all_chunks) / total_chunks if total_chunks > 0 else 0
        
        reqs = self.metrics["total_requests"]
        llm_reqs = self.metrics["llm_requests"]
        avg_ret_lat = (self.metrics["total_retrieval_latency"] / reqs) if reqs > 0 else 0
        avg_llm_lat = (self.metrics["total_llm_latency"] / llm_reqs) if llm_reqs > 0 else 0
        hit_rate = (self.metrics["cache_hits"] / reqs) if reqs > 0 else 0
        miss_rate = (self.metrics["cache_misses"] / reqs) if reqs > 0 else 0
        avg_chunks_ret = (self.metrics["total_chunks_retrieved"] / reqs) if reqs > 0 else 0
        
        return {
            "total_retrieval_requests": reqs,
            "average_retrieval_latency": round(avg_ret_lat, 4),
            "average_llm_latency": round(avg_llm_lat, 4),
            "cache_hit_rate": round(hit_rate, 2),
            "cache_miss_rate": round(miss_rate, 2),
            "documents_indexed": total_docs,
            "chunks_indexed": total_chunks,
            "average_chunks_retrieved": round(avg_chunks_ret, 1),
            "average_chunk_size": round(avg_chunk_size, 2),
            "chunk_size_configuration": self.chunk_size,
            "overlap_configuration": self.chunk_overlap,
            "retriever_type": "bm25",
            "top_k": self.top_k,
            "score_threshold": self.score_threshold,
            "cache_status": "initialized" if self._initialized else "uninitialized",
            "active_sessions": len(self._session_cache),
            "last_refresh_timestamp": self._last_refresh_time,
            "uptime_seconds": round(time.time() - getattr(self, '_start_time', time.time()), 1)
        }

    def retrieve(self, query: str, session_id: str = None) -> Tuple[str, List[str]]:
        t0 = time.time()
        self.metrics["total_requests"] += 1
        
        self._refresh_cache()
        
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
        
        if not self._all_chunks:
            self._record_latency(t0)
            return "I couldn't find relevant information in the available documents.", []

        # Tokenize and Expand
        query_tokens = _expand_query(query) if self.enable_expansion else tokenize(query)
        if not query_tokens:
            self._record_latency(t0)
            return "I couldn't find relevant information in the available documents.", []

        query_type = _analyze_query(query)

        # Session Follow-up Detection
        previous_chunks = []
        is_follow_up = False
        raw_query_words = set(re.findall(r'\b\w+\b', query.lower()))
        if self.enable_session_cache and session_id and session_id in self._session_cache:
            if raw_query_words.intersection(FOLLOW_UP_PRONOUNS):
                is_follow_up = True
                previous_chunks = self._session_cache[session_id]["chunks"]
                self.metrics["cache_hits"] += 1
                logger.info("Follow-up detected for session %s. Reusing %d chunks.", session_id, len(previous_chunks))
            else:
                self.metrics["cache_misses"] += 1
        else:
            self.metrics["cache_misses"] += 1

        # BM25 Constants
        N = len(self._all_chunks)
        avgdl = sum(len(c["tokens"]) for c in self._all_chunks) / N if N > 0 else 1
        k1 = 1.5
        b = 0.75

        # Inverse Document Frequency (using incremental _doc_freq)
        idf = {}
        for qt in query_tokens:
            n_qi = self._doc_freq.get(qt, 0)
            idf[qt] = math.log((N - n_qi + 0.5) / (n_qi + 0.5) + 1)

        # Score all chunks
        scored_chunks = []
        for chunk in self._all_chunks:
            base_score = 0.0
            doc_len = len(chunk["tokens"])
            tf = {}
            for t in chunk["tokens"]:
                tf[t] = tf.get(t, 0) + 1
            
            matched_terms = []
            for qt in query_tokens:
                if qt in tf:
                    matched_terms.append(qt)
                    f_qi = tf[qt]
                    numerator = f_qi * (k1 + 1)
                    denominator = f_qi + k1 * (1 - b + b * (doc_len / avgdl))
                    base_score += idf[qt] * (numerator / denominator)
            
            # Hybrid Filename & Worksheet Boosting
            filename_boost = 0.0
            if self.enable_filename_boost and matched_terms:
                fname_no_ext = chunk["filename_no_ext"]
                query_joined = " ".join(query_tokens).lower()
                
                if query_joined == fname_no_ext.replace("_", " ").replace("-", " "):
                    filename_boost += 5.0
                elif fname_no_ext.startswith(query_joined.replace(" ", "_")) or fname_no_ext.startswith(query_tokens[0]):
                    filename_boost += 2.0
                
                for qt in query_tokens:
                    if qt in fname_no_ext:
                        filename_boost += 1.0
                        
                # Worksheet Boosting
                sheet_name = chunk.get("sheet_name")
                if sheet_name:
                    sheet_name_lower = sheet_name.lower()
                    for qt in query_tokens:
                        if qt in sheet_name_lower:
                            filename_boost += 3.0
                            
                    if query_type == "AGGREGATE" and any(s in sheet_name_lower for s in SUMMARY_SHEETS):
                        filename_boost += 10.0
                        
                # Header Boost
                headers = chunk.get("text", "").split("\n\n")[0]
                if headers:
                    headers_lower = headers.lower()
                    for qt in query_tokens:
                        if qt in headers_lower:
                            filename_boost += 1.0
            
            final_score = base_score + filename_boost
            if final_score >= self.score_threshold:
                # Attach score for logging
                chunk["_temp_score"] = final_score
                scored_chunks.append((final_score, chunk, matched_terms))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        retrieval_mode = "BM25_TOP_K"
        dynamic_top_k = self.top_k
        target_sheet = None
        
        if query_type == "AGGREGATE" and scored_chunks:
            # The top chunk defines the target worksheet
            best_score, best_chunk, _ = scored_chunks[0]
            target_file = best_chunk.get("filepath")
            target_sheet = best_chunk.get("sheet_name")
            
            # If it belongs to a worksheet, grab all chunks from that worksheet
            if target_file and target_sheet:
                retrieval_mode = "FULL_WORKSHEET"
                # Gather all chunks from self._all_chunks for this sheet
                worksheet_chunks = [c for c in self._all_chunks if c.get("filepath") == target_file and c.get("sheet_name") == target_sheet]
                worksheet_chunks.sort(key=lambda x: x["chunk_id"])
                
                # Replace scored_chunks with these chunks
                scored_chunks = [(best_score, c, []) for c in worksheet_chunks]
                dynamic_top_k = len(scored_chunks)
            else:
                dynamic_top_k = 15 # A bit higher for aggregates if not a sheet
        elif query_type == "DETAILED":
            dynamic_top_k = 10

        # Merge previous chunks if follow-up
        selected_chunks = []
        sources = set()
        seen_chunk_ids = set()
        
        # Priority to exact BM25 matches for current query
        for score, chunk, _ in scored_chunks[:dynamic_top_k]:
            selected_chunks.append(chunk)
            seen_chunk_ids.add((chunk["filepath"], chunk["chunk_id"]))
            sources.add(chunk["filename"])
            
        # Add past chunks if we are in a follow-up and have room
        for chunk in previous_chunks:
            chunk_id_tuple = (chunk["filepath"], chunk["chunk_id"])
            if chunk_id_tuple not in seen_chunk_ids:
                selected_chunks.append(chunk)
                seen_chunk_ids.add(chunk_id_tuple)
                sources.add(chunk["filename"])

        # Enforce context bounds
        final_chunks = []
        current_context_size = 0
        final_sources = set()
        
        for chunk in selected_chunks:
            chunk_length = len(chunk["text"])
            if current_context_size + chunk_length > self.max_context_chars:
                break
            final_chunks.append(chunk)
            final_sources.add(chunk["filename"])
            current_context_size += chunk_length
            
        # Save to session cache
        if self.enable_session_cache and session_id:
            self._session_cache[session_id] = {
                "chunks": final_chunks,
                "time": time.time()
            }

        self.metrics["total_chunks_retrieved"] += len(final_chunks)
        self._record_latency(t0)

        if not final_chunks:
            return "I couldn't find relevant information in the available documents.", []

        logger.info("\n=== RAG Retrieval Debug ===")
        logger.info("Query:\n%s", query)
        logger.info("\nExpanded Query:\n%s", " ".join(query_tokens))
        logger.info("Query Type: %s", query_type)
        logger.info("Retrieval Mode: %s", retrieval_mode)
        if retrieval_mode == "FULL_WORKSHEET":
            logger.info("Detected Worksheet: %s", target_sheet)
        logger.info("\nRetrieved Chunks")
        
        for i, chunk in enumerate(final_chunks):
            score = chunk.get("_temp_score", 0.0)
            workbook = chunk.get("workbook", chunk.get("filename", "N/A"))
            sheet = chunk.get("sheet_name", "N/A")
            r_start = chunk.get("row_start", "N/A")
            r_end = chunk.get("row_end", "N/A")
            
            logger.info("\n%d.\nWorkbook: %s\nWorksheet: %s\nRow Range: %s-%s\nChunk %d\nScore: %.2f", 
                i+1, workbook, sheet, r_start, r_end, chunk["chunk_id"], score)
                
        logger.info("\nContext Size:\n%d characters", current_context_size)
        logger.info("\nTotal Chunks:\n%d", len(final_chunks))
        logger.info("===========================\n")

        # Format prompt
        sections = []
        for chunk in final_chunks:
            section = f"--------------------\nDocument:\n{chunk['filename']}\n\nChunk:\n{chunk['chunk_id']}\n\n{chunk['text']}\n--------------------"
            sections.append(section)
            
        formatted_context = "\n\n".join(sections)
        return formatted_context, sorted(list(final_sources))

    def _record_latency(self, t0: float):
        self.metrics["total_retrieval_latency"] += (time.time() - t0)
