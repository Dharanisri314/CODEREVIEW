# backend/init_memory.py
from mem0 import Memory

# Self-contained configuration matching local Qdrant (port 6333) with 768 dimensions
MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "gpt-oss:120b-cloud",
            "temperature": 0.1,
            "max_tokens": 2000,
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text:latest",
            "embedding_dims": 768,
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "codereview_memory",
            "embedding_model_dims": 768,  # Ensures 768-dim index for nomic-embed-text
        },
    },
}

def initialize_collection():
    print("🚀 Connecting to Qdrant and creating 'codereview_memory' collection...")
    try:
        # Initialize Memory directly without importing agent.py
        mem0_client = Memory.from_config(MEM0_CONFIG)
        
        # Add baseline entry to create the collection inside Qdrant
        mem0_client.add(
            "Initial setup: Code Review Agent memory initialized.",
            user_id="system_init"
        )
        print("✅ SUCCESS! 'codereview_memory' collection created successfully in Qdrant.")
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")

if __name__ == "__main__":
    initialize_collection()