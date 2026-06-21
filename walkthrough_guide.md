# 💰 PayrollPro - Employee Payroll Management System

A premium, automated employee payroll management system built with **Python (Flask)** and **SQLite**, featuring a modern, responsive web interface.

## 🚀 Key Features

### 1. **🔐 Secure Authentication**
- Robust sign-in system for both **HR** and **Employees**.
- **Invalid Credentials Detection:** Shows specific error messages for incorrect details.
- Role-based access ensures only HR can award recognitions or add employees.

### 2. **💵 Automated Payroll Engine**
- **Smart Wage Calculation:** Automatically calculates the following based on Basic Salary:
    - **HRA (House Rent Allowance):** 40% of Basic.
    - **DA (Dearness Allowance):** 30% of Basic.
    - **PF (Provident Fund):** 12% deduction.
    - **Tax:** 10% deduction (automatically applied if basic salary > ₹25,000).
    - **Professional Tax:** ₹200 flat deduction.
- **Bonus Integration:** Automatically adds ₹500 recognition bonuses to the net salary.
- **Substitution Adjustments:** Handles 25% salary transfers between employees.

### 3. **✍️ Word-to-Number Salary Entry**
- HR can enter salary in words like *"fifty thousand five hundred"* or *"35000"*.
- The system automatically parses these into numbers for database storage.
- Features a **Live Salary Preview** when adding/editing employees to confirm the parsed amount.

### 4. **🏆 Recognition & Rewards (Gamification)**
- HR can award **Employee of the Day, Week, or Year**.
- Awarding these automatically adds a **₹500 bonus** to the next payroll.
- Automated notification messages are sent to the rewarded employee's inbox.

### 5. **📋 Leave & Substitution System**
- When an employee is absent, HR can assign a **Substitute Employee**.
- **Salary Transfer:** 25% of the absent employee's daily salary for that day is automatically subtracted from them and added to the substitute.
- **Automated Messaging:** The substitute receives a notification about their new assignment and the earned bonus.

### 6. **📩 Personal Inbox**
- Every employee has a private dashboard to view their current month's **Net Salary** payslip.
- Includes a message center for substitution alerts and recognition trophies.

---

## 🛠️ Installation & Setup

1. **Wait for Dependencies:**
   Ensure `Flask`, `word2number`, and `Werkzeug` are installed:
   ```bash
   pip install Flask Werkzeug word2number
   ```

2. **Run the Application:**
   ```bash
   python app.py
   ```

3. **Login Details:**
   - **HR Admin:**
     - **Username:** `admin`
     - **Password:** `admin123`
   - **Employees:** Created by HR via the dashboard.

---

## 🏗️ Folder Structure
- `app.py`: Main Flask server and routing logic.
- `database.py`: Database schema, payroll calculations, and word-to-number logic.
- `static/style.css`: Premium dark-mode UI with glassmorphism.
- `templates/`: HTML templates for HR and Employee views.
