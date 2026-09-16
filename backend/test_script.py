import sqlite3, os

DB_PATH = "./chainlit_history.db"

# Backup warning
if os.path.exists(DB_PATH):
    print("⚠️  Existing DB found — dropping all tables and recreating...")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = OFF")

# Drop existing tables in reverse dependency order
conn.executescript("""
    DROP TABLE IF EXISTS feedbacks;
    DROP TABLE IF EXISTS elements;
    DROP TABLE IF EXISTS steps;
""")
