import sys
import os

# Add the project root to the python path so imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.embedding_service import get_embedding_model

def main():
    print("Testing EnterpriseEmbeddingClient...")
    
    try:
        emb = get_embedding_model()
        print("\nEmbedding single query: 'hello world'")
        vec = emb.embed_query("hello world")
        
        print(f"Type: {type(vec)}")
        print(f"Length: {len(vec)}")
        print(f"First 5 elements: {vec[:5]}")
        
        print("\nEmbedding batch documents...")
        docs = ["This is the first document.", "Here is another one.", "And a third document for batching."]
        vecs = emb.embed_documents(docs)
        
        print(f"Batch returned {len(vecs)} vectors.")
        for i, v in enumerate(vecs):
            print(f"Doc {i} vector length: {len(v)}")
            
        print("\nAll embedding tests passed!")
    except Exception as e:
        print(f"Error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
