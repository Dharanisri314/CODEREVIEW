# backend/view_memories.py
import json
from agent import mem0_client  # Imports your initialized local Mem0 instance

def fetch_user_memories(user_id: str):
    if not mem0_client:
        print("❌ Mem0 client is not initialized.")
        return

    print(f"\n🔍 Fetching memories for user: {user_id}...")
    
    # 1. Fetch all memory vectors stored for this user
    memories = mem0_client.get_all(user_id=user_id)
    
    print("\n--- Stored Memories ---")
    print(json.dumps(memories, indent=2))

if __name__ == "__main__":
    # Replace with the user_id you use in your application (e.g., "repo_reviewer_dev" or "default_user")
    fetch_user_memories(user_id="default_user")