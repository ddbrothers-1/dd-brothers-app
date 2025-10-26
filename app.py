
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
from datetime import datetime, date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
import sqlite3
from contextlib import closing

# ---------------- CONFIG ----------------
APP_TITLE = "DD Brothers — Transport Manager"
LOGIN_USER = "DD brothers"
LOGIN_PASS = "Ash#1Laddi"
DELETE_PASSWORD = "1322420"
DB_PATH = "db.sqlite3"
REPORTS_DIR = "reports"
COMPANY_NAME = "DD BROTHERS TRANSPORT INC."
COMPANY_ADDR = "100 Larry Cres, Caledonia ON. N3W 0C9"
COMPANY_EMAIL = "ddbrotherstrans@gmail.com"
COMPANY_PHONES = "437-985-0738, 437-219-0083"

app = Flask(__name__)
app.secret_key = "super-secret-dd-bro"

# ---------------- DB HELPERS ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(get_db()) as db:
        cur = db.cursor()
        # trucks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trucks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)
        # drivers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)
        # entries table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                is_income INTEGER NOT NULL,
                category TEXT,
                amount REAL NOT NULL,
                hst_included INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                truck_id INTEGER,
                driver_id INTEGER
            );
        """)
        db.commit()

def _ensure_dirs():
    os.makedirs(REPORTS_DIR, exist_ok=True)

# ---------------- HELPERS ----------------
def amount_with_hst(amount, hst_included):
    # If amount "includes HST", we just keep the raw amount for totals.
    # For driver pay etc, same logic you had.
    return float(amount or 0)

def totals(where="", params=()):
    q_inc = "SELECT SUM(amount) FROM entries WHERE is_income=1"
    q_exp = "SELECT SUM(amount) FROM entries WHERE is_income=0"
    if where:
        q_inc += " AND " + where
        q_exp += " AND " + where
    conn = get_db()
    ci = conn.execute(q_inc, params).fetchone()[0] or 0.0
    ce_raw = conn.execute(q_exp, params).fetchone()[0] or 0.0
    ce = ce_raw
    conn.close()
    profit = round(ci - ce, 2)
    return ci, ce, profit

# ---------------- AUTH ----------------
@app.before_request
def require_login():
    allowed = ['login', 'static', 'health']
    if request.endpoint in allowed or (request.path or "").startswith('/static'):
        return
    if not session.get('logged_in'):
        return redirect(url_for('login'))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","")
        p = request.form.get("password","")
        if u == LOGIN_USER and p == LOGIN_PASS:
            session['logged_in'] = True
            flash("Welcome.", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid login.", "warning")
    return render_template("login.html", title=APP_TITLE, no_layout=True)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))

@app.route("/health")
def health():
    return "ok", 200

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    inc, exp, prof = totals()
    return render_template("home.html", title=APP_TITLE, income=inc, expense=exp, profit=prof, LOGIN_USER=LOGIN_USER)

@app.route("/expense_income")
def expense_income():
    return render_template("expense_income.html", title=APP_TITLE, LOGIN_USER=LOGIN_USER)

@app.route("/trucks")
def trucks():
    return render_template("trucks.html", title=APP_TITLE, LOGIN_USER=LOGIN_USER)

@app.route("/drivers")
def drivers():
    return render_template("drivers.html", title=APP_TITLE, LOGIN_USER=LOGIN_USER)

@app.route("/monthly_reports")
def monthly_reports():
    return render_template("monthly_reports.html", title=APP_TITLE, LOGIN_USER=LOGIN_USER, pdf_path=None)

@app.route("/driver_pay")
def driver_pay():
    return render_template("driver_pay.html", title=APP_TITLE, LOGIN_USER=LOGIN_USER, items=[], pdf_path=None)

@app.route("/hst")
def hst_page():
    # dummy hst summary
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM entries WHERE is_income=0 AND hst_included=1"
    ).fetchall()
    conn.close()
    total_hst = 0.0
    return render_template("hst.html", title=APP_TITLE, rows=rows, total_hst=total_hst, LOGIN_USER=LOGIN_USER)

@app.route("/download_report")
def download_report():
    fname = request.args.get("fname","")
    path = os.path.join(REPORTS_DIR, fname)
    if not os.path.exists(path):
        flash("Report not found.", "warning")
        return redirect(url_for("monthly_reports"))
    return send_file(path, as_attachment=True)

# --------------- MAIN ---------------
init_db()
_ensure_dirs()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=False)
