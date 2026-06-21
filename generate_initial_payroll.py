
from database import get_db, calculate_payroll
from datetime import datetime

def generate_initial_payroll():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all employees
    employees = cursor.execute("SELECT id, basic_salary FROM employees").fetchall()
    month = datetime.now().strftime('%Y-%m')
    
    print(f"Generating payroll for {len(employees)} employees for {month}...")
    
    for emp in employees:
        emp_id = emp['id']
        basic = emp['basic_salary']
        
        # Calculate standard payroll
        data = calculate_payroll(basic)
        
        cursor.execute('''
            INSERT INTO payroll (employee_id, month, basic_salary, hra, da, pf_deduction,
                               tax_deduction, professional_tax, bonus, substitution_earning, 
                               substitution_deduction, gross_salary, total_deductions, net_salary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, month, data['basic_salary'], data['hra'], data['da'], 
              data['pf_deduction'], data['tax_deduction'], data['professional_tax'],
              data['bonus'], data['substitution_earning'], data['substitution_deduction'],
              data['gross_salary'], data['total_deductions'], data['net_salary']))
              
    conn.commit()
    conn.close()
    print("Payroll generation complete.")

if __name__ == "__main__":
    generate_initial_payroll()
