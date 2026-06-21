
import random
from database import get_db, init_db
from datetime import date, timedelta

def seed_employees():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Sample data generators
    first_names = ["Arjun", "Deepak", "Suresh", "Priya", "Ananya", "Ravi", "Amit", "Sneha", "Rahul", "Pooja", 
                   "Vikram", "Neha", "Manish", "Kavita", "Rajesh", "Sunita", "Vijay", "Aarti", "Sanjay", "Megha"]
    last_names = ["Sharma", "Verma", "Gupta", "Singh", "Yadav", "Patel", "Mishra", "Kumar", "Iyer", "Reddy",
                  "Deshmukh", "Choudhury", "Joshi", "Kulkarni", "Aggarwal", "Malhotra", "Khan", "Bose", "Das", "Jain"]
    departments = ["IT", "HR", "Finance", "Sales", "Marketing", "Operations"]
    designations = {
        "IT": ["Software Engineer", "Systems Analyst", "IT Support"],
        "HR": ["HR Manager", "Recruiter", "HR Generalist"],
        "Finance": ["Accountant", "Financial Analyst", "Finance Manager"],
        "Sales": ["Sales Executive", "Account Manager", "Regional Sales Head"],
        "Marketing": ["Marketing Associate", "Content Strategist", "SEO Lead"],
        "Operations": ["Operations Manager", "Logistics Coordinator", "Floor Supervisor"]
    }

    print("Generating 50 random employees...")

    for i in range(1, 51):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        name = f"{fname} {lname}"
        emp_code = f"EMP{1000 + i}"
        email = f"{fname.lower()}.{lname.lower()}{i}@payrollpro.com"
        phone = f"{random.randint(7000, 9999)}{random.randint(100000, 999999)}"
        dept = random.choice(departments)
        desig = random.choice(designations[dept])
        
        # Salary between 20,000 and 150,000
        salary = float(random.randint(20, 150) * 1000)
        
        # DOB between 1970 and 2000
        year = random.randint(1970, 2000)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        dob = date(year, month, day).isoformat()
        
        # Experience between 1 and 25 years
        experience = random.randint(1, 25)
        
        # Random rating 1-5
        rating = random.randint(1, 5)
        
        # Random attendance (days worked this month) 18-28 days
        attendance = random.randint(18, 28)
        
        # Joining date in the last 10 years
        doj_year = 2024 - random.randint(0, 10)
        doj = date(doj_year, random.randint(1, 12), random.randint(1, 28)).isoformat()

        # Insert Employee
        cursor.execute('''
            INSERT INTO employees (emp_code, name, email, phone, department, designation, 
                                 basic_salary, date_of_joining, dob, experience, 
                                 star_rating, attendance_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_code, name, email, phone, dept, desig, salary, doj, dob, experience, rating, attendance))
        
        emp_id = cursor.lastrowid
        
        # Create Login (Username: emp_code, Password: password123)
        username = emp_code.lower()
        password = "password123"
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, password, role, employee_id) VALUES (?, ?, 'employee', ?)",
            (username, password, emp_id)
        )

    conn.commit()
    conn.close()
    print("Done! 50 employees and their login accounts have been created.")
    print("Example Employee Login: emp1001 / password123")

if __name__ == "__main__":
    seed_employees()
