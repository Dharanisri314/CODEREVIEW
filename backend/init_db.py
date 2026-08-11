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
    DROP TABLE IF EXISTS threads;
    DROP TABLE IF EXISTS users;
""")

# Recreate with ALL columns Chainlit expects
conn.executescript("""
CREATE TABLE users (
    "id"         TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata"   TEXT NOT NULL DEFAULT '{}',
    "createdAt"  TEXT
);

CREATE TABLE threads (
    "id"             TEXT PRIMARY KEY,
    "createdAt"      TEXT,
    "name"           TEXT,
    "userId"         TEXT,
    "userIdentifier" TEXT,
    "tags"           TEXT,
    "metadata"       TEXT DEFAULT '{}',
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE steps (
    "id"              TEXT PRIMARY KEY,
    "name"            TEXT NOT NULL,
    "type"            TEXT NOT NULL,
    "threadId"        TEXT NOT NULL,
    "parentId"        TEXT,
    "streaming"       INTEGER NOT NULL DEFAULT 0,
    "waitForAnswer"   INTEGER,
    "isError"         INTEGER,
    "metadata"        TEXT DEFAULT '{}',
    "tags"            TEXT,
    "input"           TEXT,
    "output"          TEXT,
    "createdAt"       TEXT,
    "command"         TEXT,
    "start"           TEXT,
    "end"             TEXT,
    "generation"      TEXT,
    "showInput"       TEXT,
    "language"        TEXT,
    "indent"          INTEGER,
    "defaultOpen"     INTEGER,
    "disableFeedback" INTEGER,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE elements (
    "id"          TEXT PRIMARY KEY,
    "threadId"    TEXT,
    "type"        TEXT,
    "url"         TEXT,
    "chainlitKey" TEXT,
    "name"        TEXT NOT NULL,
    "display"     TEXT,
    "objectKey"   TEXT,
    "size"        TEXT,
    "page"        INTEGER,
    "language"    TEXT,
    "forId"       TEXT,
    "mime"        TEXT,
    "props"       TEXT DEFAULT '{}',
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE feedbacks (
    "id"       TEXT PRIMARY KEY,
    "forId"    TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "value"    INTEGER NOT NULL,
    "comment"  TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);
""")

conn.execute("PRAGMA foreign_keys = ON")
conn.commit()
conn.close()
print(f"✅ Schema ready at: {os.path.abspath(DB_PATH)}")

# Verify all tables exist
conn = sqlite3.connect(DB_PATH)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
conn.close()
print("Tables created:", [t[0] for t in tables])