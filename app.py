
from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3
import csv
import io
import os
from flask import send_file,flash
from werkzeug.security import generate_password_hash,check_password_hash

from datetime import date

app = Flask(__name__)
app.secret_key = "staffcentral_secret_key"
DB = "staffcentral.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empid TEXT UNIQUE,
            name TEXT,
            department TEXT,
            phone TEXT,
            email TEXT,
            joining TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empid TEXT,
            work_date TEXT,
            status TEXT,
            UNIQUE(empid, work_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_profile (
            id INTEGER PRIMARY KEY,
            name TEXT DEFAULT 'Admin',
            email TEXT DEFAULT '',
            password_hash TEXT
        )
    """)

    default_settings = {
        "theme": "purple",
        "company_name": "StaffCentral",
        "company_address": "",
        "company_phone": "",
        "date_format": "%d-%m-%Y",
        "time_format": "12",
        "default_status": "Present",
        "working_days": "Monday,Tuesday,Wednesday,Thursday,Friday",
        "office_start": "09:00",
        "office_end": "17:00",
        "attendance_notifications": "on",
        "leave_notifications": "on"
    }

    for key, value in default_settings.items():
        conn.execute("""
            INSERT OR IGNORE INTO app_settings
            (setting_key, setting_value) VALUES (?, ?)
        """, (key, value))

    conn.execute("""
        INSERT OR IGNORE INTO admin_profile
        (id, name, email, password_hash)
        VALUES (1, 'Admin', '', ?)
    """, (generate_password_hash("admin123"),))
    conn.commit()
    conn.close()


BASE = """
<!DOCTYPE html>
<html>
<head>
    <title>StaffCentral</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #F7F6FB;
            color: #24212B;
        }
        .sidebar {
            width: 245px;
            background: #191720;
            color: white;
            position: fixed;
            top: 0;
            bottom: 0;
            padding: 25px 17px;
        }
        .brand {
            font-size: 23px;
            font-weight: bold;
            margin: 5px 10px 38px;
        }
        .brand span { color: #A77AF5; }
        .menu a {
            display: block;
            padding: 14px;
            margin: 7px 0;
            color: #D8D5DF;
            text-decoration: none;
            border-radius: 9px;
        }
        .menu a:hover, .menu a.active {
            background: #7138D9;
            color: white;
        }
        .main {
            margin-left: 245px;
            padding: 28px 35px;
        }
        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        .topbar h2 { margin: 0; }
        .profile {
            background: white;
            padding: 12px 18px;
            border-radius: 10px;
        }
        .muted { color: #85808E; }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }
        .card, .panel {
            background: white;
            padding: 23px;
            border-radius: 13px;
            box-shadow: 0 3px 15px rgba(30,20,50,.05);
        }
        .card h1 { margin: 12px 0 0; font-size: 30px; }
        .purple { color: #7138D9; }
        .btn {
            display: inline-block;
            background: #7138D9;
            color: white;
            padding: 12px 18px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            font-size: 14px;
        }
        input, select {
            width: 100%;
            padding: 12px;
            margin: 8px 0 17px;
            border: 1px solid #DDD8E7;
            border-radius: 8px;
            background: white;
        }
        label { font-size: 14px; font-weight: bold; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        th, td {
            padding: 14px;
            border-bottom: 1px solid #EEEAF3;
            text-align: left;
            font-size: 14px;
        }
        th { color: #7138D9; }
        .status { color: #7138D9; font-weight: bold; }
        .bar {
            height: 12px;
            background: #7138D9;
            border-radius: 10px;
            margin: 12px 0 22px;
        }
        .login-page {
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #F7F6FB;
        }
        .login-box {
            width: 350px;
            background: white;
            padding: 35px;
            border-radius: 16px;
            box-shadow: 0 5px 25px #ddd;
        }
        @media(max-width:700px) {
            .sidebar { width: 175px; padding: 15px 8px; }
            .main { margin-left: 175px; padding: 18px 12px; }
            .brand { font-size: 18px; }
        }
        {{ theme_css|safe }}
    </style>
</head>
<body>
{% if logged_in %}
<aside class="sidebar">
    <div class="brand">💜 Staff<span>Central</span></div>
    <nav class="menu">
        <a class="{{ 'active' if active == 'Dashboard' else '' }}" href="/">▦ Dashboard</a>
        <a class="{{ 'active' if active == 'Employees' else '' }}" href="/employees">♙ Employees</a>
        <a class="{{ 'active' if active == 'Add Employee' else '' }}" href="/add">＋ Add Employee</a>
        <a class="{{ 'active' if active == 'Attendance' else '' }}" href="/attendance">◷ Attendance</a>
        <a class="{{ 'active' if active == 'Reports' else '' }}" href="/reports">▤ Reports</a>
        <a class="{{ 'active' if active == 'Settings' else '' }}" href="/settings">⚙ Settings</a>
        <a href="/logout" onclick="return confirm('Are you sure you want to logout?')">
    ↪ Logout
</a>
    </nav>
</aside>
<main class="main">
    <div class="topbar">
        <div>
            <h2>{{ active }}</h2>
            <p class="muted">Employee Attendance Management System</p>
        </div>
    <div class="profile">👤 {{ admin_name }}</div>
    </div>
    {{ content|safe }}
</main>
{% else %}
{{ content|safe }}
{% endif %}
<script>
function showReport(id) {
    document.querySelectorAll('.report-section').forEach(section => {
        section.style.display = 'none';
    });

    const target = document.getElementById(id);
    if (!target) return;

    target.style.display = 'block';

    if (id === 'overview') {
        const today = document.getElementById('today-overview');
        if (today) today.style.display = 'block';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('overview')) {
        showReport('overview');
    }
});
</script>
</body>
</html>
"""


def page(active, content):
    conn = get_db()
    settings = dict(conn.execute(
        "SELECT setting_key, setting_value FROM app_settings"
    ).fetchall())
    profile = conn.execute(
        "SELECT name FROM admin_profile WHERE id=1"
    ).fetchone()
    conn.close()

    themes = {
        "purple": ("#F7F6FB", "#191720", "#7138D9", "#FFFFFF"),
        "pink": ("#FFF5F8", "#3B202B", "#D94F91", "#FFFFFF"),
        "red": ("#FFF5F5", "#321B1B", "#D93636", "#FFFFFF"),
        "black": ("#F4F1FA", "#17131F", "#8B5CF6", "#FFFFFF"),
        "mint": ("#F1FBF7", "#18352D", "#279B75", "#FFFFFF"),
        "lavender": ("#F6F1FF", "#302442", "#9870D8", "#FFFFFF")
    }

    bg, sidebar, accent, card = themes.get(
        settings.get("theme", "purple"), themes["purple"]
    )

    theme_css = f"""
    body {{ background: {bg}; }}
    .sidebar {{ background: {sidebar}; }}
    .menu a:hover, .menu a.active, .btn {{ background: {accent}; }}
    .purple, th, .status {{ color: {accent}; }}
    .card, .panel, .profile, .login-box {{ background: {card}; }}
    .bar {{ background: {accent}; }}
    """

    return render_template_string(
        BASE,
        active=active,
        content=content,
        logged_in=("admin" in session),
        admin_name=profile["name"] if profile else "Admin",
        theme_css=theme_css
    )
@app.after_request
def prevent_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def login_required():
    return "admin" in session


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM admin_profile WHERE id=1"
        ).fetchone()
        conn.close()

        password_ok = (
            check_password_hash(admin["password_hash"], request.form.get("password", ""))
            if admin and admin["password_hash"] else False
        )

        if request.form.get("username") == "admin" and password_ok:
            session["admin"] = True
            return redirect(url_for("home"))
        return page("Login", """
        <div class="login-page"><div class="login-box">
        <h2 class="purple">Invalid login details</h2>
        <a href="/login">Try again</a>
        </div></div>
        """)
    return page("Login", """
    <div class="login-page">
      <div class="login-box">
        <h1 class="purple">💜 StaffCentral</h1>
        <p class="muted">Employee Attendance Management</p>
        <form method="POST">
          <label>Username</label>
          <input name="username" placeholder="Enter username" required>
          <label>Password</label>
          <input type="password" name="password" placeholder="Enter password" required>
          <button class="btn" style="width:100%">Login</button>
        </form>
      </div>
    </div>
    """)


@app.route("/")
def home():
    if not login_required():
        return redirect("/login")
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    today = date.today().isoformat()
    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE work_date=? AND status='Present'",
        (today,)
    ).fetchone()[0]
    absent = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE work_date=? AND status='Absent'",
        (today,)
        ).fetchone()[0]

    recent = conn.execute("""
        SELECT employees.name, attendance.empid,
               attendance.work_date, attendance.status
        FROM attendance
        JOIN employees ON employees.empid = attendance.empid
        ORDER BY attendance.work_date DESC, attendance.id DESC
        LIMIT 5
    """).fetchall()

    recent_rows = "".join(
        f"<tr><td>{r['name']}</td>"
        f"<td>{r['empid']}</td>"
        f"<td>{r['work_date']}</td>"
        f"<td class='status'>{r['status']}</td></tr>"
        for r in recent
    )

    conn.close()
    return page("Dashboard", f"""
    <p class="muted">Welcome back! Here's your office overview.</p>
    <div class="cards">
      <div class="card"><p class="muted">👥 Total Employees</p><h1>{total}</h1></div>
      <div class="card"><p class="muted">✅ Present Today</p><h1 class="purple">{present}</h1></div>
      <div class="card"><p class="muted">❌ Absent Today</p><h1>{absent}</h1></div>
    </div>
    
        <div class="panel">
      <h3>Recent Attendance</h3>
      <table>
        <tr>
          <th>Employee Name</th>
          <th>Employee ID</th>
          <th>Date</th>
          <th>Status</th>
        </tr>
        {recent_rows or '<tr><td colspan="4">No attendance records yet.</td></tr>'}
      </table>
    </div>
    """)


@app.route("/employees")
def employees():
    if not login_required():
        return redirect("/login")

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM employees ORDER BY id DESC"
    ).fetchall()
    conn.close()

    table = "".join(
        f"""
        <tr>
          <td>{r['empid']}</td>
          <td>{r['name']}</td>
          <td>{r['department']}</td>
          <td>{r['phone']}</td>
          <td>{r['email']}</td>
          <td>
            <a class="btn" href="/edit/{r['id']}">Edit</a>
            <a class="btn" href="/delete/{r['id']}"
               onclick="return confirm('Delete this employee?')">
               Delete
            </a>
          </td>
        </tr>
        """
        for r in rows
    )

    return page("Employees", f"""
    <div class="panel">
      <h3>Employee Directory</h3>
      <a class="btn" href="/add">+ Add Employee</a><br><br>

      <table>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Department</th>
          <th>Phone</th>
          <th>Email</th>
          <th>Actions</th>
        </tr>
        {table or '<tr><td colspan="6">No employees added yet.</td></tr>'}
      </table>
    </div>
    """)


@app.route("/add", methods=["GET", "POST"])
def add_employee():
    if not login_required():
        return redirect("/login")
    message = ""
    if request.method == "POST":
        try:
            conn = get_db()
            conn.execute("""
                INSERT INTO employees (empid,name,department,phone,email,joining)
                VALUES (?,?,?,?,?,?)
            """, (
                request.form["empid"], request.form["name"],
                request.form["department"], request.form["phone"],
                request.form["email"], request.form["joining"]
            ))
            conn.commit()
            conn.close()
            return redirect("/employees")
        except sqlite3.IntegrityError:
            message = "<p style='color:red'>Employee ID already exists.</p>"
    return page("Add Employee", f"""
    <div class="panel" style="max-width:650px">
      <h3>Enter Employee Details</h3>
      {message}
      <form method="POST">
        <label>Employee ID</label><input name="empid" required>
        <label>Employee Name</label><input name="name" required>
        <label>Department</label>
        <select name="department" required>
          <option value="">Select Department</option>
          <option>IT</option><option>HR</option><option>Finance</option>
          <option>Marketing</option><option>Data Science</option>
          <option>Technical Support</option>
        </select>
        <label>Phone Number</label><input name="phone" pattern="[0-9]{{10}}" maxlength="10" required>
        <label>Email</label><input type="email" name="email" required>
        <label>Joining Date</label><input type="date" name="joining" required>
        <button class="btn">Save Employee</button>
      </form>
    </div>
    """)
@app.route("/edit/<int:employee_id>", methods=["GET", "POST"])
def edit_employee(employee_id):
    if not login_required():
        return redirect("/login")

    conn = get_db()

    employee = conn.execute(
        "SELECT * FROM employees WHERE id = ?",
        (employee_id,)
    ).fetchone()

    if employee is None:
        conn.close()
        return "Employee not found"

    if request.method == "POST":
        conn.execute("""
            UPDATE employees
            SET empid=?, name=?, department=?, phone=?, email=?, joining=?
            WHERE id=?
        """, (
            request.form["empid"],
            request.form["name"],
            request.form["department"],
            request.form["phone"],
            request.form["email"],
            request.form["joining"],
            employee_id
        ))

        conn.commit()
        conn.close()
        return redirect("/employees")

    content = f"""
    <div class="panel" style="max-width:650px">
      <h3>Edit Employee Details</h3>
      <form method="POST">
        <label>Employee ID</label>
        <input name="empid" value="{employee['empid']}" required>

        <label>Employee Name</label>
        <input name="name" value="{employee['name']}" required>

        <label>Department</label>
        <select name="department" required>
          <option value="IT" {"selected" if employee['department']=="IT" else ""}>IT</option>
          <option value="HR" {"selected" if employee['department']=="HR" else ""}>HR</option>
          <option value="Finance" {"selected" if employee['department']=="Finance" else ""}>Finance</option>
          <option value="Marketing" {"selected" if employee['department']=="Marketing" else ""}>Marketing</option>
          <option value="Data Science" {"selected" if employee['department']=="Data Science" else ""}>Data Science</option>
          <option value="Technical Support" {"selected" if employee['department']=="Technical Support" else ""}>Technical Support</option>
        </select>

        <label>Phone Number</label>
        <input name="phone" value="{employee['phone']}" required>

        <label>Email</label>
        <input type="email" name="email" value="{employee['email']}" required>

        <label>Joining Date</label>
        <input type="date" name="joining" value="{employee['joining']}" required>

        <button class="btn">Update Employee</button>
      </form>
    </div>
    """

    conn.close()
    return page("Edit Employee", content)
@app.route("/delete/<int:employee_id>")
def delete_employee(employee_id):
    if not login_required():
        return redirect("/login")

    conn = get_db()

    employee = conn.execute(
        "SELECT empid FROM employees WHERE id = ?",
        (employee_id,)
    ).fetchone()

    if employee:
        conn.execute(
            "DELETE FROM attendance WHERE empid = ?",
            (employee["empid"],)
        )

        conn.execute(
            "DELETE FROM employees WHERE id = ?",
            (employee_id,)
        )

        conn.commit()

    conn.close()
    return redirect("/employees")



@app.route("/attendance", methods=["GET", "POST"])

def attendance():
    if not login_required():
        return redirect("/login")

    conn = get_db()
    message = ""

    if request.method == "POST":
        try:
            conn.execute("""
                INSERT INTO attendance (empid, work_date, status)
                VALUES (?, ?, ?)
                ON CONFLICT(empid, work_date)
                DO UPDATE SET status=excluded.status
            """, (
                request.form["empid"],
                request.form["work_date"],
                request.form["status"]
            ))
            conn.commit()
            message = "Attendance saved successfully!"
        except Exception:
            message = "Could not save attendance."

    people = conn.execute(
        "SELECT empid, name FROM employees"
    ).fetchall()

    options = "".join(
        f"<option value='{p['empid']}'>{p['empid']} - {p['name']}</option>"
        for p in people
    )

    # Filter values
    filter_date = request.args.get("filter_date", "")
    filter_status = request.args.get("filter_status", "")

    # Build attendance query
    query = """
        SELECT attendance.*, employees.name
        FROM attendance
        LEFT JOIN employees
        ON attendance.empid = employees.empid
        WHERE 1=1
    """
    params = []

    if filter_date:
        query += " AND attendance.work_date = ?"
        params.append(filter_date)

    if filter_status:
        query += " AND attendance.status = ?"
        params.append(filter_status)

    query += " ORDER BY attendance.work_date DESC"

    records = conn.execute(query, params).fetchall()

    rows = "".join(
        f"<tr><td>{r['work_date']}</td><td>{r['empid']}</td>"
        f"<td>{r['name'] or ''}</td><td>{r['status']}</td></tr>"
        for r in records
    )

    conn.close()

    return page("Attendance", f"""
    <div class="panel">
      <h3>Mark Daily Attendance</h3>
      <p class="purple">{message}</p>

      <form method="POST">
        <label>Employee</label>
        <select name="empid" required>{options}</select>

        <label>Date</label>
        <input type="date" name="work_date"
               value="{date.today()}" required>

        <label>Status</label>
        <select name="status">
          <option>Present</option>
          <option>Absent</option>
        </select>

        <button class="btn">Save Attendance</button>
      </form>
    </div>

    <br>

    <div class="panel">
      <h3>Attendance Records</h3>

      <form method="GET">
        <label>Filter by Date</label>
        <input type="date" name="filter_date"
               value="{filter_date}">

        <label>Filter by Status</label>
        <select name="filter_status">
          <option value="">All Status</option>
          <option value="Present"
            {"selected" if filter_status == "Present" else ""}>
            Present
          </option>
          <option value="Absent"
            {"selected" if filter_status == "Absent" else ""}>
            Absent
          </option>
        </select>

        <button class="btn">Apply Filter</button>
        <a class="btn" href="/attendance">Clear Filter</a>
      </form>

      <br>

      <table>
        <tr>
          <th>Date</th>
          <th>ID</th>
          <th>Name</th>
          <th>Status</th>
        </tr>
        {rows or '<tr><td colspan="4">No attendance records found.</td></tr>'}
      </table>
    </div>
    """)


@app.route("/reports")

def reports():
    if not login_required():
        return redirect("/login")

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    today = date.today().isoformat()

    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE work_date=? AND status='Present'",
        (today,)
    ).fetchone()[0]

    absent = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE work_date=? AND status='Absent'",
        (today,)
    ).fetchone()[0]

    employee_stats = conn.execute("""
        SELECT employees.empid, employees.name,
               COUNT(attendance.id) AS total_days,
               SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) AS present_days,
               SUM(CASE WHEN attendance.status='Absent' THEN 1 ELSE 0 END) AS absent_days
        FROM employees
        LEFT JOIN attendance
        ON employees.empid = attendance.empid
        GROUP BY employees.empid, employees.name
    """).fetchall()
    selected_month = request.args.get(
        "month", date.today().strftime("%Y-%m")
    )

    monthly_stats = conn.execute("""
        SELECT employees.empid, employees.name,
               COUNT(attendance.id) AS total_days,
               SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) AS present_days,
               SUM(CASE WHEN attendance.status='Absent' THEN 1 ELSE 0 END) AS absent_days
        FROM employees
        LEFT JOIN attendance
        ON employees.empid = attendance.empid
        AND attendance.work_date LIKE ?
        GROUP BY employees.empid, employees.name
    """, (selected_month + "%",)).fetchall()

    employee_rows = ""

    monthly_total = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance
        WHERE work_date LIKE ?
    """, (selected_month + "%",)).fetchone()

    overall_present = monthly_total["present"] or 0
    overall_absent = monthly_total["absent"] or 0
    overall_total = overall_present + overall_absent

    overall_percentage = (
        (overall_present / overall_total) * 100
        if overall_total > 0 else 0
    )
    monthly_rows = ""

    for r in monthly_stats:
        total_days = r["total_days"]
        present_days = r["present_days"] or 0
        absent_days = r["absent_days"] or 0

        percentage = (
            (present_days / total_days) * 100
            if total_days > 0 else 0
        )

        monthly_rows += f"""
        <tr>
          <td>{r['empid']}</td>
          <td>{r['name']}</td>
          <td>{present_days}</td>
          <td>{absent_days}</td>
          <td>{percentage:.1f}%</td>
        </tr>
        """


    for r in employee_stats:
        total_days = r["total_days"]
        present_days = r["present_days"] or 0
        absent_days = r["absent_days"] or 0

        percentage = (
            (present_days / total_days) * 100
            if total_days > 0 else 0
        )

        employee_rows += f"""
        <tr>
          <td>{r['empid']}</td>
          <td>{r['name']}</td>
          <td>{present_days}</td>
          <td>{absent_days}</td>
          <td>{percentage:.1f}%</td>
        </tr>
        """
        daily_records = conn.execute("""
        SELECT attendance.work_date, attendance.empid,
               employees.name, attendance.status
        FROM attendance
        LEFT JOIN employees
        ON attendance.empid = employees.empid
        ORDER BY attendance.work_date DESC
    """).fetchall()

    daily_rows = ""

    for r in daily_records:
        daily_rows += f"""
        <tr>
          <td>{r['work_date']}</td>
          <td>{r['empid']}</td>
          <td>{r['name'] or ''}</td>
          <td>{r['status']}</td>
        </tr>
        """

    conn.close()

    maximum = max(total, 1)

    return page("Reports", f"""
    <div class="report-tabs">
     <button class="btn" type="button" onclick="showReport('overview')">Overview</button>
     <button class="btn" type="button" onclick="showReport('employee-overview')">Employee Overview</button>
     <button class="btn" type="button" onclick="showReport('monthly')">Monthly Attendance</button>
     <button class="btn" type="button" onclick="showReport('daily')">Daily Records</button>
    </div>    
    <div class="cards report-section" id="overview">
      <div class="card"><p>Total Employees</p><h1>{total}</h1></div>
      <div class="card"><p>Present Today</p><h1 class="purple">{present}</h1></div>
      <div class="card"><p>Absent Today</p><h1>{absent}</h1></div>
    </div>

    <div class="panel report-section" id="today-overview">
      <h3>Today's Attendance Overview</h3>
      <p>Present: {present}</p>
      <div class="bar" style="width:{min(present/maximum*100,100)}%"></div>
      <p>Absent: {absent}</p>
      <div class="bar" style="width:{min(absent/maximum*100,100)}%"></div>
    </div>
        <div class="panel report-section" id="monthly">
      <h3>Monthly Attendance Report</h3>
            <div class="cards">
        <div class="card">
          <p>Total Attendance</p>
          <h1>{overall_total}</h1>
        </div>

        <div class="card">
          <p>Present</p>
          <h1 class="purple">{overall_present}</h1>
        </div>

        <div class="card">
          <p>Absent</p>
          <h1>{overall_absent}</h1>
        </div>

        <div class="card">
          <p>Overall Attendance</p>
          <h1>{overall_percentage:.1f}%</h1>
        </div>
      </div>

      <form method="GET">
        <label>Select Month</label>
        <input type="month" name="month" value="{selected_month}" required>
        <button class="btn">View Report</button>
      </form>

      <br>

      <table>
        <tr>
          <th>Employee ID</th>
          <th>Name</th>
          <th>Present</th>
          <th>Absent</th>
          <th>Attendance %</th>
        </tr>
        {monthly_rows or '<tr><td colspan="5">No records found.</td></tr>'}
      </table>
    </div>

    <div class="panel report-section" id="employee-overview">
      <h3>Employee-wise Attendance Report</h3>
      <table>
        <tr>
          <th>Employee ID</th>
          <th>Name</th>
          <th>Present</th>
          <th>Absent</th>
          <th>Attendance %</th>
        </tr>
        {employee_rows or '<tr><td colspan="5">No employees found.</td></tr>'}
      </table>
    </div>
    <div class="panel report-section" id="daily">
      <h3>Daily Attendance Records</h3>
      <table>
        <tr>
          <th>Date</th>
          <th>Employee ID</th>
          <th>Name</th>
          <th>Status</th>
        </tr>
        {daily_rows or '<tr><td colspan="4">No records found.</td></tr>'}
      </table>
    </div>
    """)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not login_required():
        return redirect("/login")

    conn = get_db()
    message = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_general":
            values = {
                "theme": request.form.get("theme", "purple"),
                "company_name": request.form.get("company_name", ""),
                "company_address": request.form.get("company_address", ""),
                "company_phone": request.form.get("company_phone", ""),
                "date_format": request.form.get("date_format", "%d-%m-%Y"),
                "time_format": request.form.get("time_format", "12"),
                "default_status": request.form.get("default_status", "Present"),
                "working_days": ",".join(request.form.getlist("working_days")),
                "office_start": request.form.get("office_start", "09:00"),
                "office_end": request.form.get("office_end", "17:00"),
                "attendance_notifications": request.form.get("attendance_notifications", "off"),
                "leave_notifications": request.form.get("leave_notifications", "off")
            }

            for key, value in values.items():
                conn.execute("""
                    INSERT INTO app_settings (setting_key, setting_value)
                    VALUES (?, ?)
                    ON CONFLICT(setting_key)
                    DO UPDATE SET setting_value=excluded.setting_value
                """, (key, value))

            conn.commit()
            message = "Settings saved successfully!"

        elif action == "save_profile":
            conn.execute("""
                UPDATE admin_profile
                SET name=?, email=?
                WHERE id=1
            """, (
                request.form.get("name", "Admin"),
                request.form.get("email", "")
            ))
            conn.commit()
            message = "Profile updated successfully!"

        elif action == "change_password":
            admin = conn.execute(
                "SELECT password_hash FROM admin_profile WHERE id=1"
            ).fetchone()

            current = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")

            if not check_password_hash(admin["password_hash"], current):
                message = "Current password is incorrect."
            elif len(new_password) < 8:
                message = "New password must contain at least 8 characters."
            elif new_password != confirm:
                message = "New passwords do not match."
            else:
                conn.execute("""
                    UPDATE admin_profile
                    SET password_hash=?
                    WHERE id=1
                """, (generate_password_hash(new_password),))
                conn.commit()
                message = "Password changed successfully!"

        elif action == "reset":
            defaults = {
                "theme": "purple",
                "company_name": "StaffCentral",
                "company_address": "",
                "company_phone": "",
                "date_format": "%d-%m-%Y",
                "time_format": "12",
                "default_status": "Present",
                "working_days": "Monday,Tuesday,Wednesday,Thursday,Friday",
                "office_start": "09:00",
                "office_end": "17:00",
                "attendance_notifications": "on",
                "leave_notifications": "on"
            }

            for key, value in defaults.items():
                conn.execute("""
                    UPDATE app_settings
                    SET setting_value=?
                    WHERE setting_key=?
                """, (value, key))

            conn.commit()
            message = "Settings restored to defaults!"

    settings_data = dict(conn.execute(
        "SELECT setting_key, setting_value FROM app_settings"
    ).fetchall())

    profile = conn.execute(
        "SELECT name, email FROM admin_profile WHERE id=1"
    ).fetchone()

    conn.close()

    working_days = settings_data.get("working_days", "").split(",")

    def selected(key, value):
        return "selected" if settings_data.get(key) == value else ""

    def checked(value):
        return "checked" if value in working_days else ""

    return page("Settings", f"""
    <style>
      .settings-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit,minmax(280px,1fr));
        gap: 20px;
      }}
      .settings-panel {{ margin-bottom: 20px; }}
      .settings-panel h3 {{ margin-top: 0; }}
      .settings-panel input, .settings-panel select,
      .settings-panel textarea {{ width:100%; }}
      .days label {{ display:inline-block; margin:8px 12px 8px 0; }}
      .days input {{ width:auto; margin:0 5px 0 0; }}
      .settings-message {{ color:#279B75; font-weight:bold; }}
    </style>

    <p class="settings-message">{message}</p>

    <form method="POST">
      <input type="hidden" name="action" value="save_general">

      <div class="settings-panel panel">
        <h3>🎨 Appearance</h3>
        <label>Choose Website Theme</label>
        <select name="theme">
          <option value="purple" {selected("theme","purple")}>Purple & White</option>
          <option value="pink" {selected("theme","pink")}>Pink & White</option>
          <option value="red" {selected("theme","red")}>Red & White</option>
          <option value="black" {selected("theme","black")}>Black & Purple</option>
          <option value="mint" {selected("theme","mint")}>Mint Green & White</option>
          <option value="lavender" {selected("theme","lavender")}>Lavender & White</option>
        </select>
        <p class="muted">Your selected theme will apply across the website.</p>
      </div>

      <div class="settings-grid">
        <div class="settings-panel panel">
          <h3>🏢 Company Details</h3>
          <label>Company Name</label>
          <input name="company_name" value="{settings_data.get('company_name','')}" required>
          <label>Address</label>
          <textarea name="company_address" rows="3">{settings_data.get('company_address','')}</textarea>
          <label>Contact Number</label>
          <input name="company_phone" value="{settings_data.get('company_phone','')}">
        </div>

        <div class="settings-panel panel">
          <h3>📅 Date & Time</h3>
          <label>Date Format</label>
          <select name="date_format">
            <option value="%d-%m-%Y" {selected("date_format","%d-%m-%Y")}>DD-MM-YYYY</option>
            <option value="%m-%d-%Y" {selected("date_format","%m-%d-%Y")}>MM-DD-YYYY</option>
            <option value="%Y-%m-%d" {selected("date_format","%Y-%m-%d")}>YYYY-MM-DD</option>
          </select>
          <label>Time Format</label>
          <select name="time_format">
            <option value="12" {selected("time_format","12")}>12-hour</option>
            <option value="24" {selected("time_format","24")}>24-hour</option>
          </select>
        </div>

        <div class="settings-panel panel">
          <h3>🕒 Attendance Settings</h3>
          <label>Default Attendance Status</label>
          <select name="default_status">
            <option value="Present" {selected("default_status","Present")}>Present</option>
            <option value="Absent" {selected("default_status","Absent")}>Absent</option>
          </select>
          <label>Office Start Time</label>
          <input type="time" name="office_start" value="{settings_data.get('office_start','09:00')}">
          <label>Office End Time</label>
          <input type="time" name="office_end" value="{settings_data.get('office_end','17:00')}">
          <label>Working Days</label>
          <div class="days">
            {''.join(f'<label><input type="checkbox" name="working_days" value="{day}" {checked(day)}>{day}</label>' for day in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])}
          </div>
        </div>

        <div class="settings-panel panel">
          <h3>🔔 Notifications</h3>
          <label>
            <input type="checkbox" name="attendance_notifications" value="on"
              style="width:auto" {"checked" if settings_data.get("attendance_notifications")=="on" else ""}>
            Attendance Notifications
          </label>
          <br><br>
          <label>
            <input type="checkbox" name="leave_notifications" value="on"
              style="width:auto" {"checked" if settings_data.get("leave_notifications")=="on" else ""}>
            Leave Notifications
          </label>
          <p class="muted">These preferences are saved for future notification integration.</p>
        </div>
      </div>

      <button class="btn">Save All Settings</button>
    </form>

    <div class="settings-grid" style="margin-top:20px">
      <div class="panel settings-panel">
        <h3>👤 Admin Profile</h3>
        <form method="POST">
          <input type="hidden" name="action" value="save_profile">
          <label>Admin Name</label>
          <input name="name" value="{profile['name']}" required>
          <label>Email</label>
          <input type="email" name="email" value="{profile['email']}">
          <button class="btn">Update Profile</button>
        </form>
      </div>

      <div class="panel settings-panel">
        <h3>🔐 Change Password</h3>
        <form method="POST">
          <input type="hidden" name="action" value="change_password">
          <label>Current Password</label>
          <input type="password" name="current_password" required>
          <label>New Password</label>
          <input type="password" name="new_password" minlength="8" required>
          <label>Confirm New Password</label>
          <input type="password" name="confirm_password" minlength="8" required>
          <button class="btn">Change Password</button>
        </form>
      </div>
    </div>

    <div class="panel settings-panel">
      <h3>💾 Data Management</h3>
      <p>Download a copy of your database or export employee records.</p>
      <a class="btn" href="/settings/backup">Download Database Backup</a>
      <a class="btn" href="/settings/export">Export Employees CSV</a>
    </div>

    <div class="panel settings-panel">
      <h3>♻ Reset Settings</h3>
      <p class="muted">Restore settings to their default values.</p>
      <form method="POST" onsubmit="return confirm('Reset all settings to defaults?')">
        <input type="hidden" name="action" value="reset">
        <button class="btn" type="submit">Reset Settings</button>
      </form>
    </div>
    """)
@app.route("/settings/backup")
def settings_backup():
    if not login_required():
        return redirect("/login")

    if not os.path.exists(DB):
        return "Database file not found.", 404

    return send_file(
        DB,
        as_attachment=True,
        download_name="staffcentral_backup.db"
    )


@app.route("/settings/export")
def settings_export():
    if not login_required():
        return redirect("/login")

    conn = get_db()
    rows = conn.execute("""
        SELECT empid, name, department, phone, email, joining
        FROM employees
        ORDER BY id
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee ID", "Name", "Department",
        "Phone", "Email", "Joining Date"
    ])

    for row in rows:
        writer.writerow(list(row))

    memory_file = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="text/csv",
        as_attachment=True,
        download_name="staffcentral_employees.csv"
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
