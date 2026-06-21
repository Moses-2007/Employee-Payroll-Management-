"""
PayrollPro - Employee Payroll Management System
Main Flask Application
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import (
    get_db, init_db, calculate_payroll, words_to_number,
    calculate_substitution_amount, send_substitution_message,
    get_recognition_bonus, get_substitution_earnings, get_substitution_deductions
)
from datetime import datetime, date
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'payrollpro_secret_key_2026'


# ─── AUTH DECORATORS ──────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'hr':
            flash('Access denied. HR privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ─── AUTH ROUTES ──────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('⚠️ Invalid Credentials! Please enter both username and password.', 'error')
            return render_template('login.html')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['employee_id'] = user['employee_id']
            flash(f'Welcome back, {user["username"]}! 🎉', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Invalid Credentials! Wrong username or password.', 'error')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ─── DASHBOARD ────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    role = session.get('role')

    if role == 'hr':
        # HR Dashboard stats
        total_employees = conn.execute("SELECT COUNT(*) as c FROM employees WHERE is_active = 1").fetchone()['c']
        total_payrolls = conn.execute("SELECT COUNT(*) as c FROM payroll").fetchone()['c']
        pending_leaves = conn.execute("SELECT COUNT(*) as c FROM leave_substitution WHERE status = 'accepted'").fetchone()['c']
        
        # NEW: Fetch actual pending requests for HR to act on
        pending_approvals = conn.execute(
            """SELECT ls.*, e1.name as absent_name, e2.name as substitute_name 
               FROM leave_substitution ls
               JOIN employees e1 ON ls.absent_employee_id = e1.id
               JOIN employees e2 ON ls.substitute_employee_id = e2.id
               WHERE ls.status = 'accepted' 
               ORDER BY ls.created_at DESC"""
        ).fetchall()

        recognitions = conn.execute(
            "SELECT r.*, e.name FROM recognition r JOIN employees e ON r.employee_id = e.id ORDER BY r.created_at DESC LIMIT 5"
        ).fetchall()
        recent_employees = conn.execute(
            "SELECT * FROM employees WHERE is_active = 1 ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        conn.close()
        return render_template('hr_dashboard.html',
                               total_employees=total_employees,
                               total_payrolls=total_payrolls,
                               pending_leaves=pending_leaves,
                               pending_approvals=pending_approvals,
                               recognitions=recognitions,
                               recent_employees=recent_employees)
    else:
        # Employee Dashboard
        emp_id = session.get('employee_id')
        employee = None
        payroll = None
        messages = []
        recognitions = []
        substitution_alert = None

        if emp_id:
            employee = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
            payroll = conn.execute(
                "SELECT * FROM payroll WHERE employee_id = ? ORDER BY generated_at DESC LIMIT 1",
                (emp_id,)
            ).fetchone()
            messages = conn.execute(
                "SELECT * FROM messages WHERE recipient_employee_id = ? ORDER BY created_at DESC LIMIT 5",
                (emp_id,)
            ).fetchall()
            recognitions = conn.execute(
                "SELECT * FROM recognition WHERE employee_id = ? ORDER BY recognized_date DESC LIMIT 5",
                (emp_id,)
            ).fetchall()
            
            # Find if this employee is currently substituting today
            active_sub = conn.execute(
                """SELECT ls.*, e.name as absent_name 
                   FROM leave_substitution ls 
                   JOIN employees e ON ls.absent_employee_id = e.id 
                   WHERE ls.substitute_employee_id = ? AND ls.status = 'approved' 
                   AND ls.leave_date = ?""",
                (emp_id, date.today().isoformat())
            ).fetchone()
            
            if active_sub:
                substitution_alert = f"u are substituted in place of {active_sub['absent_name']} due to reason of {active_sub['reason'] or 'leave'}."

            # NEW: Find substitution requests waiting for THIS employee to accept/decline
            pending_sub_requests = conn.execute(
                """SELECT ls.*, e.name as absent_name 
                   FROM leave_substitution ls 
                   JOIN employees e ON ls.absent_employee_id = e.id 
                   WHERE ls.substitute_employee_id = ? AND ls.status = 'pending'""",
                (emp_id,)
            ).fetchall()

            # CHECK: If this employee is marked ABSENT today
            is_absent_today = conn.execute(
                "SELECT * FROM attendance_logs WHERE employee_id = ? AND log_date = ?",
                (emp_id, date.today().isoformat())
            ).fetchone()

        conn.close()
        return render_template('emp_dashboard.html',
                               employee=employee, payroll=payroll,
                               messages=messages, recognitions=recognitions,
                               substitution_alert=substitution_alert,
                               pending_sub_requests=pending_sub_requests,
                               is_absent_today=is_absent_today)


# ─── EMPLOYEE MANAGEMENT (HR) ────────────────────────────────────────

@app.route('/employees')
@hr_required
def employees():
    conn = get_db()
    today = date.today().isoformat()
    
    # Fetch employees and check if they are absent today
    emps = conn.execute(
        """SELECT e.*, 
           (SELECT 1 FROM attendance_logs WHERE employee_id = e.id AND log_date = ?) as is_absent_today
           FROM employees e ORDER BY e.name""",
        (today,)
    ).fetchall()
    conn.close()
    return render_template('employees.html', employees=emps)


@app.route('/employee/add', methods=['GET', 'POST'])
@hr_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        emp_code = request.form.get('emp_code', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        salary_input = request.form.get('basic_salary', '').strip()
        doj = request.form.get('date_of_joining', '').strip()
        create_login = request.form.get('create_login')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not name or not emp_code or not salary_input:
            flash('⚠️ Invalid details! Name, Employee Code, and Basic Salary are required.', 'error')
            return render_template('add_employee.html')

        # Convert salary from words to number
        basic_salary = words_to_number(salary_input)
        if basic_salary <= 0:
            flash('⚠️ Invalid Salary! Could not parse the salary value. Enter a valid number or words like "fifty thousand".', 'error')
            return render_template('add_employee.html')

        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO employees (emp_code, name, email, phone, department, designation, basic_salary, date_of_joining)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (emp_code, name, email, phone, department, designation, basic_salary, doj or None)
            )
            emp_id = cursor.lastrowid

            # Create login credentials if requested
            if create_login and username and password:
                cursor.execute(
                    "INSERT INTO users (username, password, role, employee_id) VALUES (?, ?, 'employee', ?)",
                    (username, password, emp_id)
                )

            conn.commit()
            flash(f'✅ Employee {name} added successfully! Salary: ₹{basic_salary:,.2f} (entered as: "{salary_input}")', 'success')
            return redirect(url_for('employees'))
        except sqlite3.IntegrityError as e:
            flash(f'⚠️ Invalid details! Employee code or username already exists.', 'error')
        except Exception as e:
            flash(f'⚠️ Error: {str(e)}', 'error')
        finally:
            conn.close()

    return render_template('add_employee.html')


@app.route('/employee/edit/<int:emp_id>', methods=['GET', 'POST'])
@hr_required
def edit_employee(emp_id):
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        salary_input = request.form.get('basic_salary', '').strip()
        star_rating = request.form.get('star_rating', 0)

        basic_salary = words_to_number(salary_input)
        if basic_salary <= 0:
            flash('⚠️ Invalid Salary!', 'error')
            emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
            conn.close()
            return render_template('edit_employee.html', employee=emp)

        conn.execute(
            """UPDATE employees SET name=?, email=?, phone=?, department=?, designation=?, basic_salary=?, star_rating=?
               WHERE id=?""",
            (name, email, phone, department, designation, basic_salary, star_rating, emp_id)
        )
        conn.commit()
        flash(f'✅ Employee updated! Salary: ₹{basic_salary:,.2f}', 'success')
        conn.close()
        return redirect(url_for('employees'))

    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    conn.close()
    return render_template('edit_employee.html', employee=emp)


@app.route('/employee/deactivate/<int:emp_id>')
@hr_required
def deactivate_employee(emp_id):
    conn = get_db()
    conn.execute("UPDATE employees SET is_active = 0 WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    flash('Employee deactivated.', 'info')
    return redirect(url_for('employees'))


# ─── PAYROLL ──────────────────────────────────────────────────────────

@app.route('/payroll')
@login_required
def payroll():
    conn = get_db()
    role = session.get('role')

    if role == 'hr':
        payrolls = conn.execute(
            """SELECT p.*, e.name, e.emp_code, e.department
               FROM payroll p JOIN employees e ON p.employee_id = e.id
               ORDER BY p.generated_at DESC"""
        ).fetchall()
        employees_list = conn.execute("SELECT id, name, emp_code FROM employees WHERE is_active = 1").fetchall()
        conn.close()
        return render_template('payroll.html', payrolls=payrolls, employees=employees_list)
    else:
        emp_id = session.get('employee_id')
        payrolls = conn.execute(
            "SELECT * FROM payroll WHERE employee_id = ? ORDER BY generated_at DESC",
            (emp_id,)
        ).fetchall()
        conn.close()
        return render_template('payroll.html', payrolls=payrolls, employees=[])


@app.route('/payroll/generate', methods=['POST'])
@hr_required
def generate_payroll():
    emp_id = request.form.get('employee_id')
    month = request.form.get('month', datetime.now().strftime('%Y-%m'))

    conn = get_db()
    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()

    if not emp:
        flash('⚠️ Invalid Employee!', 'error')
        conn.close()
        return redirect(url_for('payroll'))

    # Get bonuses and substitution amounts
    bonus = get_recognition_bonus(int(emp_id), month)
    sub_earn = get_substitution_earnings(int(emp_id), month)
    sub_deduct = get_substitution_deductions(int(emp_id), month)

    payroll_data = calculate_payroll(emp['basic_salary'], bonus, sub_earn, sub_deduct)

    conn.execute(
        """INSERT INTO payroll (employee_id, month, basic_salary, hra, da, pf_deduction,
           tax_deduction, professional_tax, bonus, substitution_earning, substitution_deduction,
           gross_salary, total_deductions, net_salary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (emp_id, month, payroll_data['basic_salary'], payroll_data['hra'],
         payroll_data['da'], payroll_data['pf_deduction'], payroll_data['tax_deduction'],
         payroll_data['professional_tax'], payroll_data['bonus'],
         payroll_data['substitution_earning'], payroll_data['substitution_deduction'],
         payroll_data['gross_salary'], payroll_data['total_deductions'],
         payroll_data['net_salary'])
    )
    conn.commit()
    conn.close()
    flash(f'✅ Payroll generated for {emp["name"]}! Net Salary: ₹{payroll_data["net_salary"]:,.2f}', 'success')
    return redirect(url_for('payroll'))


# ─── RECOGNITION (Employee of Day/Week/Year) ─────────────────────────

@app.route('/recognition')
@login_required
def recognition():
    conn = get_db()
    recognitions = conn.execute(
        """SELECT r.*, e.name, e.emp_code, e.department 
           FROM recognition r JOIN employees e ON r.employee_id = e.id
           ORDER BY r.recognized_date DESC"""
    ).fetchall()
    employees_list = conn.execute("SELECT id, name, emp_code FROM employees WHERE is_active = 1").fetchall()
    conn.close()
    return render_template('recognition.html', recognitions=recognitions, employees=employees_list)


@app.route('/recognition/award', methods=['POST'])
@hr_required
def award_recognition():
    emp_id = request.form.get('employee_id')
    rec_type = request.form.get('recognition_type')
    notes = request.form.get('notes', '').strip()
    rec_date = request.form.get('recognition_date', date.today().isoformat())

    if not emp_id or not rec_type:
        flash('⚠️ Invalid details! Select employee and recognition type.', 'error')
        return redirect(url_for('recognition'))

    conn = get_db()
    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()

    if not emp:
        flash('⚠️ Invalid Employee!', 'error')
        conn.close()
        return redirect(url_for('recognition'))

    conn.execute(
        """INSERT INTO recognition (employee_id, recognition_type, recognized_date, bonus_amount, awarded_by, notes)
           VALUES (?, ?, ?, 500, ?, ?)""",
        (emp_id, rec_type, rec_date, session['user_id'], notes)
    )

    # Send congratulations message
    type_label = {'day': 'Day', 'week': 'Week', 'year': 'Year'}.get(rec_type, rec_type)
    conn.execute(
        "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
        (emp_id,
         f"🏆 Congratulations! Employee of the {type_label}!",
         f"Dear {emp['name']},\n\nCongratulations! You have been selected as the Employee of the {type_label}! "
         f"A bonus of ₹500 has been added to your salary.\n\n{('Note: ' + notes) if notes else ''}\n\nRegards,\nHR Department",
         'recognition')
    )

    conn.commit()
    conn.close()
    flash(f'🏆 {emp["name"]} awarded Employee of the {type_label}! ₹500 bonus added.', 'success')
    return redirect(url_for('recognition'))


# ─── LEAVE & SUBSTITUTION ────────────────────────────────────────────

@app.route('/leave')
@login_required
def leave():
    conn = get_db()
    role = session.get('role')

    if role == 'hr':
        leaves = conn.execute(
            """SELECT ls.*, e1.name as absent_name, e1.emp_code as absent_code,
                      e2.name as substitute_name, e2.emp_code as substitute_code
               FROM leave_substitution ls
               JOIN employees e1 ON ls.absent_employee_id = e1.id
               JOIN employees e2 ON ls.substitute_employee_id = e2.id
               ORDER BY ls.created_at DESC"""
        ).fetchall()
    else:
        emp_id = session.get('employee_id')
        leaves = conn.execute(
            """SELECT ls.*, e1.name as absent_name, e1.emp_code as absent_code,
                      e2.name as substitute_name, e2.emp_code as substitute_code
               FROM leave_substitution ls
               JOIN employees e1 ON ls.absent_employee_id = e1.id
               JOIN employees e2 ON ls.substitute_employee_id = e2.id
               WHERE ls.absent_employee_id = ? OR ls.substitute_employee_id = ?
               ORDER BY ls.created_at DESC""",
            (emp_id, emp_id)
        ).fetchall()

    employees_list = conn.execute("SELECT id, name, emp_code FROM employees WHERE is_active = 1").fetchall()
    conn.close()
    return render_template('leave.html', leaves=leaves, employees=employees_list)


@app.route('/leave/apply', methods=['POST'])
@login_required
def apply_leave():
    absent_id = request.form.get('absent_employee_id')
    substitute_id = request.form.get('substitute_employee_id')
    leave_date = request.form.get('leave_date')
    reason = request.form.get('reason', '').strip()

    if not absent_id or not substitute_id or not leave_date:
        flash('⚠️ Invalid details! All fields are required.', 'error')
        return redirect(url_for('leave'))

    if absent_id == substitute_id:
        flash('⚠️ Invalid details! Absent and substitute employee cannot be the same.', 'error')
        return redirect(url_for('leave'))

    conn = get_db()
    absent_emp = conn.execute("SELECT * FROM employees WHERE id = ?", (absent_id,)).fetchone()

    if not absent_emp:
        flash('⚠️ Invalid Employee!', 'error')
        conn.close()
        return redirect(url_for('leave'))

    # Calculate 25% of daily salary
    transfer_amount = calculate_substitution_amount(absent_emp['basic_salary'])

    conn.execute(
        """INSERT INTO leave_substitution (absent_employee_id, substitute_employee_id, leave_date,
           reason, salary_transfer_amount, status) VALUES (?, ?, ?, ?, ?, 'pending')""",
        (absent_id, substitute_id, leave_date, reason, transfer_amount)
    )
    conn.commit()
    conn.close()

    flash(f'📋 Leave applied! ₹{transfer_amount:.2f} will be transferred to substitute upon approval.', 'success')
    return redirect(url_for('leave'))


@app.route('/leave/approve/<int:leave_id>')
@hr_required
def approve_leave(leave_id):
    conn = get_db()
    leave_record = conn.execute("SELECT * FROM leave_substitution WHERE id = ?", (leave_id,)).fetchone()

    if leave_record:
        if leave_record['status'] != 'accepted':
            flash('⚠️ HR can only approve requests that have been accepted by the substitute.', 'warning')
        else:
            conn.execute("UPDATE leave_substitution SET status = 'approved', message_sent = 1 WHERE id = ?", (leave_id,))
            
            # AUTOMATICALLY MARK ABSENT and decrease attendance count
            absent_emp_id = leave_record['absent_employee_id']
            leave_date = leave_record['leave_date']
            
            conn.execute("UPDATE employees SET attendance_count = attendance_count - 1 WHERE id = ?", (absent_emp_id,))
            conn.execute("INSERT OR IGNORE INTO attendance_logs (employee_id, log_date, status) VALUES (?, ?, 'absent')", 
                         (absent_emp_id, leave_date))
            
            # Notify absent employee
            conn.execute(
                "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
                (absent_emp_id, "✅ Leave Approved", 
                 f"Your leave request for {leave_date} has been approved. You are marked as absent and protected by your substitute.", 
                 'notification')
            )
            
            conn.commit()

            # Final confirmation message to substitute
            send_substitution_message(
                leave_record['absent_employee_id'],
                leave_record['substitute_employee_id'],
                leave_record['leave_date'],
                leave_record['salary_transfer_amount']
            )
            flash('✅ Leave fully approved and employee marked as absent!', 'success')
    else:
        flash('⚠️ Leave record not found.', 'error')

    conn.close()
    return redirect(url_for('leave'))


@app.route('/leave/substitute/accept/<int:leave_id>')
@login_required
def substitute_accept(leave_id):
    conn = get_db()
    leave_record = conn.execute("SELECT * FROM leave_substitution WHERE id = ?", (leave_id,)).fetchone()
    
    if leave_record and leave_record['substitute_employee_id'] == session.get('employee_id'):
        conn.execute("UPDATE leave_substitution SET status = 'accepted' WHERE id = ?", (leave_id,))
        
        # Notify the absent employee
        substitute_name = session.get('username')
        conn.execute(
            "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
            (leave_record['absent_employee_id'], 
             "✅ Substitution Accepted!", 
             f"Good news! Your substitute has accepted your request for {leave_record['leave_date']}. It is now waiting for HR approval.", 
             'notification')
        )
        conn.commit()
        flash('You have accepted the substitution request.', 'success')
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/leave/substitute/decline/<int:leave_id>')
@login_required
def substitute_decline(leave_id):
    conn = get_db()
    leave_record = conn.execute("SELECT * FROM leave_substitution WHERE id = ?", (leave_id,)).fetchone()
    
    if leave_record and leave_record['substitute_employee_id'] == session.get('employee_id'):
        conn.execute("UPDATE leave_substitution SET status = 'declined' WHERE id = ?", (leave_id,))
        
        # Notify the absent employee
        conn.execute(
            "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
            (leave_record['absent_employee_id'], 
             "❌ Substitution Declined", 
             f"Unfortunately, your substitution request for {leave_record['leave_date']} was declined. Please find another substitute.", 
             'error')
        )
        conn.commit()
        flash('Substitution request declined.', 'info')
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/employee/mark-absent/<int:emp_id>')
@hr_required
def mark_absent(emp_id):
    conn = get_db()
    today = date.today().isoformat()
    
    # Check if already marked
    existing = conn.execute("SELECT * FROM attendance_logs WHERE employee_id = ? AND log_date = ?", (emp_id, today)).fetchone()
    
    if not existing:
        conn.execute("UPDATE employees SET attendance_count = attendance_count - 1 WHERE id = ?", (emp_id,))
        conn.execute("INSERT INTO attendance_logs (employee_id, log_date, status) VALUES (?, ?, 'absent')", (emp_id, today))
        
        # Notify the employee
        conn.execute(
            "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
            (emp_id, "📍 Marked Absent", "You have been marked as ABSENT for today by HR. Please contact your manager if this is an error.", 'error')
        )
        conn.commit()
        flash('Employee marked as absent and notified.', 'info')
    else:
        flash('Employee is already marked as absent for today.', 'warning')
        
    conn.close()
    return redirect(url_for('employees'))


@app.route('/leave/reject/<int:leave_id>')
@hr_required
def reject_leave(leave_id):
    conn = get_db()
    leave_record = conn.execute("SELECT * FROM leave_substitution WHERE id = ?", (leave_id,)).fetchone()
    
    if leave_record:
        conn.execute("UPDATE leave_substitution SET status = 'rejected' WHERE id = ?", (leave_id,))
        
        # Notify BOTH parties
        # 1. Notify Absent Employee
        conn.execute(
            "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
            (leave_record['absent_employee_id'], "❌ Leave Rejected by HR", 
             f"Your leave request for {leave_record['leave_date']} has been rejected by HR. Please contact your manager for details.", 
             'error')
        )
        
        # 2. Notify Substitute
        conn.execute(
            "INSERT INTO messages (recipient_employee_id, subject, body, message_type) VALUES (?, ?, ?, ?)",
            (leave_record['substitute_employee_id'], "🚫 Substitution Cancelled", 
             f"The substitution request for {leave_record['absent_employee_id']} on {leave_record['leave_date']} was rejected by HR. You are no longer required to substitute.", 
             'info')
        )
        
        conn.commit()
        flash('Leave request rejected and both parties have been notified.', 'info')
    else:
        flash('Leave record not found.', 'error')
        
    conn.close()
    return redirect(url_for('leave'))


# ─── MESSAGES ─────────────────────────────────────────────────────────

@app.route('/messages')
@login_required
def messages():
    conn = get_db()
    emp_id = session.get('employee_id')
    if emp_id:
        msgs = conn.execute(
            "SELECT * FROM messages WHERE recipient_employee_id = ? ORDER BY created_at DESC",
            (emp_id,)
        ).fetchall()
        # Mark as read
        conn.execute(
            "UPDATE messages SET is_read = 1 WHERE recipient_employee_id = ?",
            (emp_id,)
        )
        conn.commit()
    else:
        msgs = []
    conn.close()
    return render_template('messages.html', messages=msgs)


@app.route('/messages/count')
@login_required
def unread_count():
    emp_id = session.get('employee_id')
    if emp_id:
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) as c FROM messages WHERE recipient_employee_id = ? AND is_read = 0",
            (emp_id,)
        ).fetchone()['c']
        conn.close()
        return jsonify({'count': count})
    return jsonify({'count': 0})


# ─── SALARY PREVIEW (AJAX) ───────────────────────────────────────────

@app.route('/api/salary-preview', methods=['POST'])
@login_required
def salary_preview():
    salary_input = request.json.get('salary', '')
    numeric_val = words_to_number(salary_input)
    if numeric_val > 0:
        payroll_data = calculate_payroll(numeric_val)
        return jsonify({
            'success': True,
            'numeric_value': numeric_val,
            'formatted': f'₹{numeric_val:,.2f}',
            'payroll': payroll_data
        })
    return jsonify({'success': False, 'message': 'Could not convert salary'})


# ─── ERROR HANDLERS ──────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template('login.html'), 404


# ─── MAIN ─────────────────────────────────────────────────────────────

import sqlite3

if __name__ == '__main__':
    init_db()
    print("\n" + "="*60)
    print("  PayrollPro - Employee Payroll Management System")
    print("  Running at: http://127.0.0.1:5000")
    print("  Default HR Login: admin / admin123")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
