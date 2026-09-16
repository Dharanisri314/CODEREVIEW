from mem0 import Memory

# Configuration to run Mem0 completely offline with Ollama & local Qdrant vector store
MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.1:latest",
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
            "path": "./mem0_qdrant_db",  # Stores vectors locally inside backend/mem0_qdrant_db
        },
    },
}

# Initialize Mem0 instance
memory_client = Memory.from_config(MEM0_CONFIG)

def get_memories(user_id: str, query: str = "") -> str:
    """Search stored coding rules/preferences for a given user."""
    results = memory_client.search(query=query, user_id=user_id)
    if not results or not results.get("results"):
        return ""
    
    extracted_memories = [item["memory"] for item in results["results"]]
    return "\n".join(f"- {m}" for m in extracted_memories)

def save_memory(user_id: str, text: str, metadata: dict = None):
    """Save user preferences or repo standards to long-term memory."""
    memory_client.add(text, user_id=user_id, metadata=metadata)