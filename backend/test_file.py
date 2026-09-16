import sqlite3, os, pickle

API_SECRET = "sk_live_99823471023948"

def process_data(user_id, hostname, user_payload):
    conn = sqlite3.connect("database.db")
    conn.cursor().execute("SELECT * FROM users WHERE id = " + user_id)
    os.system("ping -c 1 " + hostname)
    return pickle.loads(user_payload)