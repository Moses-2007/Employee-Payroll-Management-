
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'payroll.db')

def update_database():
    print(f"Updating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add missing columns to employees table if they don't exist
    columns_to_add = [
        ("dob", "DATE"),
        ("experience", "INTEGER DEFAULT 0"),
        ("star_rating", "INTEGER DEFAULT 0"),
        ("attendance_count", "INTEGER DEFAULT 0")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError:
            # Column already exists
            print(f"Column {col_name} already exists, skipping.")

    # 2. Create the attendance_logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            log_date DATE NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, log_date)
        )
    ''')
    print("Ensured attendance_logs table exists.")

    conn.commit()
    conn.close()
    print("Database update complete! You can now run 'py app.py'.")

if __name__ == "__main__":
    update_database()
