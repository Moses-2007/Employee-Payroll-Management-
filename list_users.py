import sqlite3
import os

DB_PATH = 'payroll.db'

def list_users():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        users = cursor.execute("SELECT id, username, password, role FROM users").fetchall()
        print("Users in database:")
        for user in users:
            print(f"ID: {user['id']}, Username: {user['username']}, Password: {user['password']}, Role: {user['role']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_users()
