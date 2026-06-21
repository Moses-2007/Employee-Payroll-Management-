"""
Database module for PayrollPro - Employee Payroll Management System.
Handles all database operations including setup, CRUD, payroll, recognition, and substitution.
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'payroll.db')


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database with all required tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Users table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            employee_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department TEXT,
            designation TEXT,
            basic_salary REAL NOT NULL DEFAULT 0,
            date_of_joining DATE,
            dob DATE,
            experience INTEGER DEFAULT 0,
            star_rating INTEGER DEFAULT 0,
            attendance_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Payroll table (auto-calculated)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            basic_salary REAL NOT NULL,
            hra REAL NOT NULL,
            da REAL NOT NULL,
            pf_deduction REAL NOT NULL,
            tax_deduction REAL NOT NULL,
            professional_tax REAL NOT NULL DEFAULT 200,
            bonus REAL NOT NULL DEFAULT 0,
            substitution_earning REAL NOT NULL DEFAULT 0,
            substitution_deduction REAL NOT NULL DEFAULT 0,
            gross_salary REAL NOT NULL,
            total_deductions REAL NOT NULL,
            net_salary REAL NOT NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')

    # Employee recognition (Employee of Day/Week/Year)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recognition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            recognition_type TEXT NOT NULL,
            recognized_date DATE NOT NULL,
            bonus_amount REAL NOT NULL DEFAULT 500,
            awarded_by INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (awarded_by) REFERENCES users(id)
        )
    ''')

    # Leave and substitution table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_substitution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            absent_employee_id INTEGER NOT NULL,
            substitute_employee_id INTEGER NOT NULL,
            leave_date DATE NOT NULL,
            reason TEXT,
            salary_transfer_amount REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            message_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (absent_employee_id) REFERENCES employees(id),
            FOREIGN KEY (substitute_employee_id) REFERENCES employees(id)
        )
    ''')

    # Messages/notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_employee_id INTEGER NOT NULL,
            sender_name TEXT DEFAULT 'System',
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            message_type TEXT DEFAULT 'notification',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recipient_employee_id) REFERENCES employees(id)
        )
    ''')

    # Attendance logs for tracking daily absence
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            log_date DATE NOT NULL,
            status TEXT NOT NULL, -- 'absent'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, log_date)
        )
    ''')
    
    # Create default HR user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ('admin', 'admin123', 'hr')
        )

    conn.commit()
    conn.close()


# ─── PAYROLL CALCULATION ───────────────────────────────────────────────

def calculate_payroll(basic_salary, bonus=0, sub_earning=0, sub_deduction=0):
    """
    Auto-calculate all payroll components from basic salary.
    HRA = 40% of Basic
    DA = 30% of Basic
    PF = 12% of Basic
    Tax = 10% of Basic (if basic > 25000)
    Professional Tax = ₹200
    """
    hra = round(basic_salary * 0.40, 2)
    da = round(basic_salary * 0.30, 2)
    pf = round(basic_salary * 0.12, 2)
    tax = round(basic_salary * 0.10, 2) if basic_salary > 25000 else 0
    prof_tax = 200.0

    gross = round(basic_salary + hra + da + bonus + sub_earning, 2)
    total_deductions = round(pf + tax + prof_tax + sub_deduction, 2)
    net = round(gross - total_deductions, 2)

    return {
        'basic_salary': basic_salary,
        'hra': hra,
        'da': da,
        'pf_deduction': pf,
        'tax_deduction': tax,
        'professional_tax': prof_tax,
        'bonus': bonus,
        'substitution_earning': sub_earning,
        'substitution_deduction': sub_deduction,
        'gross_salary': gross,
        'total_deductions': total_deductions,
        'net_salary': net
    }


# ─── WORD-TO-NUMBER SALARY CONVERSION ─────────────────────────────────

def words_to_number(text):
    """
    Convert salary entered as words into numeric value.
    E.g. 'fifty thousand' → 50000, 'thirty five thousand five hundred' → 35500
    Falls back to direct numeric conversion if not words.
    """
    if text is None:
        return 0.0

    text = str(text).strip()

    # If it's already a number
    try:
        return float(text.replace(',', ''))
    except ValueError:
        pass

    # Try word-to-number conversion
    try:
        from word2number import w2n
        return float(w2n.word_to_num(text))
    except Exception:
        pass

    # Manual fallback for common patterns
    text_lower = text.lower().strip()
    word_map = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
        'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90
    }
    multipliers = {
        'hundred': 100, 'thousand': 1000, 'lakh': 100000,
        'lakhs': 100000, 'crore': 10000000, 'crores': 10000000
    }

    words = text_lower.replace('-', ' ').replace(' and ', ' ').split()
    current = 0
    result = 0

    for word in words:
        if word in word_map:
            current += word_map[word]
        elif word in multipliers:
            if current == 0:
                current = 1
            current *= multipliers[word]
            if word in ('thousand', 'lakh', 'lakhs', 'crore', 'crores'):
                result += current
                current = 0

    result += current
    return float(result) if result > 0 else 0.0


# ─── SUBSTITUTION HELPERS ─────────────────────────────────────────────

def calculate_substitution_amount(basic_salary):
    """Calculate 25% of daily salary for substitution."""
    daily_salary = basic_salary / 30.0
    return round(daily_salary * 0.25, 2)


def send_substitution_message(absent_emp_id, substitute_emp_id, leave_date, amount):
    """Send notification to substitute employee about the substitution."""
    conn = get_db()
    cursor = conn.cursor()

    # Get names
    cursor.execute("SELECT name FROM employees WHERE id = ?", (absent_emp_id,))
    absent_name = cursor.fetchone()['name']

    cursor.execute("SELECT name FROM employees WHERE id = ?", (substitute_emp_id,))
    sub_name = cursor.fetchone()['name']

    subject = f"📋 Substitution Assignment - {leave_date}"
    body = (
        f"Dear {sub_name},\n\n"
        f"You have been assigned as a substitute for {absent_name} on {leave_date}.\n"
        f"An additional amount of ₹{amount:.2f} (25% of daily salary) will be added to your salary.\n\n"
        f"Please cover their responsibilities for the day.\n\n"
        f"Regards,\nHR Department"
    )

    cursor.execute(
        "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
        (substitute_emp_id, subject, body, 'substitution')
    )
    conn.commit()
    conn.close()


# ─── RECOGNITION HELPERS ──────────────────────────────────────────────

def get_recognition_bonus(employee_id, month=None):
    """Get total recognition bonus for an employee in a given month."""
    conn = get_db()
    cursor = conn.cursor()
    if month:
        cursor.execute(
            "SELECT COALESCE(SUM(bonus_amount), 0) as total FROM recognition WHERE employee_id = ? AND strftime('%Y-%m', recognized_date) = ?",
            (employee_id, month)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(bonus_amount), 0) as total FROM recognition WHERE employee_id = ?",
            (employee_id,)
        )
    total = cursor.fetchone()['total']
    conn.close()
    return total


def get_substitution_earnings(employee_id, month=None):
    """Get total substitution earnings for an employee."""
    conn = get_db()
    cursor = conn.cursor()
    if month:
        cursor.execute(
            "SELECT COALESCE(SUM(salary_transfer_amount), 0) as total FROM leave_substitution WHERE substitute_employee_id = ? AND strftime('%Y-%m', leave_date) = ? AND status = 'approved'",
            (employee_id, month)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(salary_transfer_amount), 0) as total FROM leave_substitution WHERE substitute_employee_id = ? AND status = 'approved'",
            (employee_id,)
        )
    total = cursor.fetchone()['total']
    conn.close()
    return total


def get_substitution_deductions(employee_id, month=None):
    """Get total substitution deductions for an absent employee."""
    conn = get_db()
    cursor = conn.cursor()
    if month:
        cursor.execute(
            "SELECT COALESCE(SUM(salary_transfer_amount), 0) as total FROM leave_substitution WHERE absent_employee_id = ? AND strftime('%Y-%m', leave_date) = ? AND status = 'approved'",
            (employee_id, month)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(salary_transfer_amount), 0) as total FROM leave_substitution WHERE absent_employee_id = ? AND status = 'approved'",
            (employee_id,)
        )
    total = cursor.fetchone()['total']
    conn.close()
    return total
