import sqlite3
from datetime import datetime, date
import os

DB_PATH = os.getenv("DB_PATH", "hr_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            branch      TEXT NOT NULL,
            position    TEXT NOT NULL,
            hourly_rate INTEGER DEFAULT 0,
            language    TEXT DEFAULT 'uz',
            role        TEXT DEFAULT 'employee',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date   TEXT NOT NULL,
            check_in    TEXT,
            lunch_out   TEXT,
            lunch_in    TEXT,
            check_out   TEXT,
            lat_in      REAL,
            lon_in      REAL,
            lat_out     REAL,
            lon_out     REAL,
            is_late     INTEGER DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE (employee_id, work_date)
        );

        CREATE TABLE IF NOT EXISTS vacation_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date  TEXT NOT NULL,
            end_date    TEXT NOT NULL,
            reason      TEXT,
            status      TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );
        """)


# ── Employee ──────────────────────────────────────────────────────────────────

def get_employee(telegram_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return dict(row) if row else None


def get_employee_by_id(emp_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (emp_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_employees():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_employee_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]


def add_employee(telegram_id, name, branch, position, language="uz", role="employee"):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO employees (telegram_id, name, branch, position, language, role)
               VALUES (?,?,?,?,?,?)""",
            (telegram_id, name, branch, position, language, role),
        )


def update_employee_language(telegram_id: int, language: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE employees SET language=? WHERE telegram_id=?",
            (language, telegram_id),
        )


def update_employee_rate(emp_id: int, rate: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE employees SET hourly_rate=? WHERE id=?", (rate, emp_id)
        )


def set_admin(telegram_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE employees SET role='admin' WHERE telegram_id=?", (telegram_id,)
        )


# ── Attendance ────────────────────────────────────────────────────────────────

def get_today_attendance(emp_id: int, work_date: str = None):
    if work_date is None:
        work_date = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
            (emp_id, work_date),
        ).fetchone()
    return dict(row) if row else None


def mark_check_in(emp_id: int, lat=None, lon=None, is_late=0):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO attendance (employee_id, work_date, check_in, lat_in, lon_in, is_late)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(employee_id, work_date) DO UPDATE SET
               check_in=excluded.check_in, lat_in=excluded.lat_in,
               lon_in=excluded.lon_in, is_late=excluded.is_late""",
            (emp_id, today, now, lat, lon, is_late),
        )
    return now


def mark_lunch_out(emp_id: int):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "UPDATE attendance SET lunch_out=? WHERE employee_id=? AND work_date=?",
            (now, emp_id, today),
        )
    return now


def mark_lunch_in(emp_id: int):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "UPDATE attendance SET lunch_in=? WHERE employee_id=? AND work_date=?",
            (now, emp_id, today),
        )
    return now


def mark_check_out(emp_id: int, lat=None, lon=None):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """UPDATE attendance SET check_out=?, lat_out=?, lon_out=?
               WHERE employee_id=? AND work_date=?""",
            (now, lat, lon, emp_id, today),
        )
    return now


def get_month_stats(emp_id: int, year: int, month: int):
    prefix = f"{year}-{month:02d}"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date LIKE ?",
            (emp_id, f"{prefix}%"),
        ).fetchall()
    records = [dict(r) for r in rows]

    total_minutes = 0
    came = 0
    late = 0

    for r in records:
        if r["check_in"]:
            came += 1
        if r["is_late"]:
            late += 1
        if r["check_in"] and r["check_out"]:
            t_in = datetime.strptime(r["check_in"], "%H:%M:%S")
            t_out = datetime.strptime(r["check_out"], "%H:%M:%S")
            lunch_min = 0
            if r["lunch_out"] and r["lunch_in"]:
                lo = datetime.strptime(r["lunch_out"], "%H:%M:%S")
                li = datetime.strptime(r["lunch_in"], "%H:%M:%S")
                lunch_min = (li - lo).seconds // 60
            total_minutes += (t_out - t_in).seconds // 60 - lunch_min

    return {
        "total_hours": total_minutes / 60,
        "came": came,
        "late": late,
        "records": records,
    }


def get_attendance_history(emp_id: int, limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM attendance WHERE employee_id=?
               ORDER BY work_date DESC LIMIT ?""",
            (emp_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Vacation ──────────────────────────────────────────────────────────────────

def add_vacation_request(emp_id: int, start_date: str, end_date: str, reason: str = ""):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO vacation_requests (employee_id, start_date, end_date, reason)
               VALUES (?,?,?,?)""",
            (emp_id, start_date, end_date, reason),
        )
        return cur.lastrowid


def get_my_vacations(emp_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM vacation_requests WHERE employee_id=? ORDER BY created_at DESC",
            (emp_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_vacations():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT v.*, e.name, e.branch, e.telegram_id
               FROM vacation_requests v
               JOIN employees e ON e.id = v.employee_id
               WHERE v.status='pending'
               ORDER BY v.created_at""",
        ).fetchall()
    return [dict(r) for r in rows]


def update_vacation_status(req_id: int, status: str, reviewed_by: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE vacation_requests SET status=?, reviewed_by=? WHERE id=?",
            (status, reviewed_by, req_id),
        )
