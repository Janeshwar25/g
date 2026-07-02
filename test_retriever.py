import sys
import os
import logging

# Configure basic logging for visibility
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Add the project root to the python path so imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import Config
from agent.bm25_retriever import BM25Retriever

def main():
    print("Initializing BM25 Retriever...\n")
    cfg = Config()
    retriever = BM25Retriever(cfg)
    
    # Run a few queries
    queries = [
        "What is PMAT?",
        "How do I update a project plan?",
        "Who is the default BDL?",
        "this is a garbage query 1234567890"
    ]
    
    for q in queries:
        print(f"\n====================\nQuery: {q}\n====================")
        context, sources = retriever.retrieve(q)
        
        print("\n--- Retrieved Sources ---")
        for src in sources:
            print(f"✓ {src}")
            
        print("\n--- Prompt Context ---")
        # Print just a snippet if it's too long
        if len(context) > 1000:
            print(context[:1000] + "\n...[truncated]...")
        else:
            print(context)

if __name__ == "__main__":
    main()
