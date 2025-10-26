from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
import sqlite3, os
from contextlib import closing
from datetime import datetime, date
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

APP_TITLE = "DD Brothers — Transport Manager"
DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite3")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
COMPANY_NAME = "DD BROTHERS TRANSPORT INC."
COMPANY_ADDR = "100 Larry Cres, Caledonia ON. N3W 0C9"
COMPANY_EMAIL = "ddbrotherstrans@gmail.com"
COMPANY_PHONES = "437-985-0738, 437-219-0083"
DELETE_PASSWORD = "1322420"
LOGIN_USER = "DD brothers"
LOGIN_PASS = "Ash#1Laddi"
LOGO_PATH = os.path.join("static","dd_logo.png")

app = Flask(__name__)
app.secret_key = "ddbros-secret"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS trucks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS drivers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT NOT NULL,
        is_income INTEGER NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        hst_included INTEGER NOT NULL DEFAULT 0,
        description TEXT NOT NULL,
        truck_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL,
        FOREIGN KEY(truck_id) REFERENCES trucks(id),
        FOREIGN KEY(driver_id) REFERENCES drivers(id)
    );""")
    conn.commit()
    conn.close()

def amount_with_hst(amount, hst_inc):
    # expense amount entered could be with or without HST (13%)
    if hst_inc:
        return round(float(amount),2)
    else:
        return round(float(amount),2)

def totals(extra_where=None, params=()):
    conn = get_db()
    cur = conn.cursor()
    base = "FROM entries "
    if extra_where:
        base += "WHERE "+extra_where
    cur.execute("SELECT SUM(amount) "+base+" AND is_income=1" if extra_where else "SELECT SUM(amount) "+base+" WHERE is_income=1", params)
    inc = cur.fetchone()[0] or 0.0
    cur.execute("SELECT SUM(amount) "+base+" AND is_income=0" if extra_where else "SELECT SUM(amount) "+base+" WHERE is_income=0", params)
    exp = cur.fetchone()[0] or 0.0
    conn.close()
    return (round(inc,2), round(exp,2), round(inc-exp,2))

@app.before_request
def require_login():
    allowed = ['login','static','download_report','health']
    if request.endpoint in allowed or (request.path or '').startswith('/static'):
        return
    if not session.get('logged_in'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username','')
        p = request.form.get('password','')
        if u == LOGIN_USER and p == LOGIN_PASS:
            session['logged_in']=True
            flash("Logged in.","success")
            return redirect(url_for('home'))
        flash("Wrong password.","warning")
    return render_template('login.html', title=APP_TITLE, login_user=LOGIN_USER)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out","info")
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return 'ok',200

def draw_footer(c):
    c.setFont("Helvetica",8)
    c.setFillColorRGB(0.40,0.40,0.40)
    footer = f"{COMPANY_NAME}  |  {COMPANY_ADDR}  |  {COMPANY_EMAIL}  |  {COMPANY_PHONES}"
    c.drawCentredString(4.25*inch,0.55*inch,footer)
    c.setFillColor(colors.black)

def header_pdf(c,title):
    logo = os.path.join(os.path.dirname(__file__),LOGO_PATH)
    if os.path.exists(logo):
        c.drawImage(logo,0.6*inch,9.6*inch,width=1.1*inch,height=1.1*inch,preserveAspectRatio=True,mask='auto')
    c.setFont("Helvetica-Bold",14)
    c.drawCentredString(4.25*inch,10.4*inch,COMPANY_NAME)
    c.setFont("Helvetica",10)
    c.drawCentredString(4.25*inch,10.15*inch,COMPANY_ADDR)
    c.drawCentredString(4.25*inch,9.95*inch,f"{COMPANY_EMAIL}    {COMPANY_PHONES}")
    c.line(0.6*inch,9.8*inch,7.9*inch,9.8*inch)
    c.setFont("Helvetica-Bold",12)
    c.drawCentredString(4.25*inch,9.55*inch,title)
    c.setFont("Helvetica-Bold",10)
    c.drawCentredString(4.25*inch,9.35*inch,f"Generated on: {datetime.now().strftime('%B %d, %Y')}")
    draw_footer(c)

@app.route('/')
def home():
    conn = get_db()
    income,expense,profit = totals()
    cur = conn.cursor()
    cur.execute("""SELECT e.*, t.name AS truck_name, d.name AS driver_name
                    FROM entries e
                    LEFT JOIN trucks t ON e.truck_id=t.id
                    LEFT JOIN drivers d ON e.driver_id=d.id
                    ORDER BY date(entry_date) DESC, id DESC
                    LIMIT 10""")
    recent = cur.fetchall()
    conn.close()
    return render_template('home.html', title=APP_TITLE, income=income, expense=expense, profit=profit, recent=recent)

@app.route('/expense_income', methods=['GET','POST'])
def expense_income():
    conn = get_db(); cur = conn.cursor()
    if request.method=='POST':
        mode = request.form.get('mode')  # income or expense
        entry_date = request.form.get('entry_date')
        truck_id = request.form.get('truck_id') or None
        driver_id = request.form.get('driver_id') or None
        desc = request.form.get('description','').strip()
        errors=[]
        if not entry_date: errors.append("Date is required")
        if not truck_id: errors.append("Truck is required")
        if not driver_id: errors.append("Driver is required")
        if not desc: errors.append("Description is required")

        if mode=='income':
            is_income=1
            category='Income'
            amount=float(request.form.get('income_amount') or 0)
            hst_included=1
            if amount<=0: errors.append("Income amount must be > 0")
        else:
            is_income=0
            category=request.form.get('expense_category') or 'Other'
            if category.lower().strip()=='driver income':
                category='Driver Pay'
            amount=float(request.form.get('expense_amount') or 0)
            hst_included=1 if request.form.get('hst_option')=='with' else 0
            if amount<=0: errors.append("Expense amount must be > 0")

        if errors:
            for e in errors: flash(e,'warning')
            conn.close()
            return redirect(url_for('expense_income'))

        cur.execute("""INSERT INTO entries(entry_date,is_income,category,amount,hst_included,description,truck_id,driver_id)
                        VALUES(?,?,?,?,?,?,?,?)""",
                    (entry_date,is_income,category,amount,hst_included,desc,truck_id,driver_id))
        conn.commit()
        flash("Saved!","success")
        conn.close()
        return redirect(url_for('expense_income'))

    cur.execute("SELECT * FROM trucks ORDER BY name"); trucks=cur.fetchall()
    cur.execute("SELECT * FROM drivers ORDER BY name"); drivers=cur.fetchall()

    q_from=request.args.get('from'); q_to=request.args.get('to')
    where=""; params=[]
    if q_from:
        where += (" WHERE date(entry_date)>=?" if not where else " AND date(entry_date)>=?")
        params.append(q_from)
    if q_to:
        where += (" WHERE date(entry_date)<=?" if not where else " AND date(entry_date)<=?")
        params.append(q_to)

    cur.execute(f"""SELECT e.*, t.name AS truck_name, d.name AS driver_name
                 FROM entries e
                 LEFT JOIN trucks t ON e.truck_id=t.id
                 LEFT JOIN drivers d ON e.driver_id=d.id
                 {where}
                 ORDER BY date(entry_date) DESC, id DESC
                 LIMIT 200""", params)
    entries=cur.fetchall()
    conn.close()
    return render_template('expense_income.html', title=APP_TITLE, trucks=trucks, drivers=drivers, entries=entries)

@app.route('/entry/<int:id>/delete', methods=['POST'])
def delete_entry(id):
    pwd=request.form.get('delete_password','')
    if pwd!=DELETE_PASSWORD:
        flash("Wrong deletion password.","warning")
        return redirect(url_for('expense_income'))
    conn=get_db()
    conn.execute("DELETE FROM entries WHERE id=?",(id,))
    conn.commit(); conn.close()
    flash("Entry deleted.","info")
    return redirect(url_for('expense_income'))

@app.route('/entry/<int:id>/edit', methods=['GET','POST'])
def edit_entry(id):
    conn=get_db(); cur=conn.cursor()
    if request.method=='POST':
        entry_date=request.form.get('entry_date')
        is_income=int(request.form.get('is_income'))
        category=request.form.get('category')
        if category.lower().strip()=='driver income':
            category='Driver Pay'
        amount=float(request.form.get('amount') or 0)
        hst_included=int(request.form.get('hst_included') or 0)
        desc=request.form.get('description','').strip()
        truck_id=request.form.get('truck_id') or None
        driver_id=request.form.get('driver_id') or None

        errors=[]
        if not entry_date: errors.append("Date is required")
        if amount<=0: errors.append("Amount must be > 0")
        if not truck_id: errors.append("Truck is required")
        if not driver_id: errors.append("Driver is required")
        if not desc: errors.append("Description is required")

        if errors:
            for e in errors: flash(e,'warning')
            conn.close()
            return redirect(url_for('edit_entry',id=id))

        cur.execute("""UPDATE entries SET entry_date=?, is_income=?, category=?, amount=?, hst_included=?, description=?, truck_id=?, driver_id=? WHERE id=?""",
            (entry_date,is_income,category,amount,hst_included,desc,truck_id,driver_id,id))
        conn.commit(); conn.close()
        flash("Entry updated.","success")
        return redirect(url_for('expense_income'))

    cur.execute("SELECT * FROM entries WHERE id=?",(id,)); entry=cur.fetchone()
    cur.execute("SELECT * FROM trucks ORDER BY name"); trucks=cur.fetchall()
    cur.execute("SELECT * FROM drivers ORDER BY name"); drivers=cur.fetchall()
    conn.close()
    return render_template('edit_entry.html', title=APP_TITLE, entry=entry, trucks=trucks, drivers=drivers)

@app.route('/trucks', methods=['GET','POST'])
def trucks():
    conn=get_db(); cur=conn.cursor()
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if name:
            try:
                cur.execute("INSERT INTO trucks(name) VALUES(?)",(name,))
                conn.commit()
                flash("Truck added.","success")
            except sqlite3.IntegrityError:
                flash("Truck already exists.","warning")
        return redirect(url_for('trucks'))
    cur.execute("SELECT * FROM trucks ORDER BY name")
    items=cur.fetchall()
    conn.close()
    return render_template('trucks.html', title=APP_TITLE, items=items)

@app.route('/trucks/<int:id>/delete', methods=['POST'])
def delete_truck(id):
    pwd=request.form.get('delete_password','')
    if pwd!=DELETE_PASSWORD:
        flash("Wrong deletion password.","warning")
        return redirect(url_for('trucks'))
    conn=get_db()
    conn.execute("DELETE FROM trucks WHERE id=?",(id,))
    conn.commit(); conn.close()
    flash("Truck deleted.","info")
    return redirect(url_for('trucks'))

@app.route('/trucks/<int:id>/edit', methods=['POST'])
def edit_truck(id):
    name=request.form.get('name','').strip()
    conn=get_db()
    conn.execute("UPDATE trucks SET name=? WHERE id=?",(name,id))
    conn.commit(); conn.close()
    flash("Truck updated.","success")
    return redirect(url_for('trucks'))

@app.route('/drivers', methods=['GET','POST'])
def drivers():
    conn=get_db(); cur=conn.cursor()
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if name:
            try:
                cur.execute("INSERT INTO drivers(name) VALUES(?)",(name,))
                conn.commit()
                flash("Driver added.","success")
            except sqlite3.IntegrityError:
                flash("Driver already exists.","warning")
        return redirect(url_for('drivers'))
    cur.execute("SELECT * FROM drivers ORDER BY name")
    items=cur.fetchall()
    conn.close()
    return render_template('drivers.html', title=APP_TITLE, items=items)

@app.route('/drivers/<int:id>/delete', methods=['POST'])
def delete_driver(id):
    pwd=request.form.get('delete_password','')
    if pwd!=DELETE_PASSWORD:
        flash("Wrong deletion password.","warning")
        return redirect(url_for('drivers'))
    conn=get_db()
    conn.execute("DELETE FROM drivers WHERE id=?",(id,))
    conn.commit(); conn.close()
    flash("Driver deleted.","info")
    return redirect(url_for('drivers'))

@app.route('/drivers/<int:id>/edit', methods=['POST'])
def edit_driver(id):
    name=request.form.get('name','').strip()
    conn=get_db()
    conn.execute("UPDATE drivers SET name=? WHERE id=?",(name,id))
    conn.commit(); conn.close()
    flash("Driver updated.","success")
    return redirect(url_for('drivers'))

@app.route('/hst')
def hst():
    conn=get_db(); cur=conn.cursor()
    cur.execute("""SELECT entry_date, description, amount,
                      ROUND(amount*13.0/113.0,2) AS hst_component
                   FROM entries
                   WHERE is_income=0 AND hst_included=1
                   ORDER BY date(entry_date) DESC, id DESC""")
    rows=cur.fetchall()
    total_hst=sum([r['hst_component'] or 0 for r in rows])
    conn.close()
    return render_template('hst.html', title=APP_TITLE, rows=rows, total_hst=total_hst)

@app.route('/monthly_reports', methods=['GET','POST'])
def monthly_reports():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT * FROM trucks ORDER BY name")
    trucks=cur.fetchall()
    pdf_path=None
    if request.method=='POST':
        truck_id=request.form.get('truck_id')
        month=int(request.form.get('month'))
        year=int(request.form.get('year'))
        start=date(year,month,1)
        end=date(year+(1 if month==12 else 0),1 if month==12 else month+1,1)

        if truck_id=='all':
            cur.execute("""SELECT e.*, t.id AS truck_id, t.name AS truck_name, d.name AS driver_name
                            FROM entries e
                            LEFT JOIN trucks t ON e.truck_id=t.id
                            LEFT JOIN drivers d ON e.driver_id=d.id
                            WHERE date(entry_date)>=? AND date(entry_date)<?
                            ORDER BY t.name ASC, date(entry_date) ASC, e.id ASC""",(str(start),str(end)))
            rows=cur.fetchall()
            if not rows:
                flash("No data available for the selected month.","warning")
                conn.close()
                return render_template('monthly_reports.html', title=APP_TITLE, trucks=trucks, pdf_path=None)

            groups={}
            for r in rows:
                key=(r['truck_id'], r['truck_name'] or '—')
                groups.setdefault(key,[]).append(r)

            filename=f"Monthly_Report_{start.strftime('%Y_%m')}_All_Trucks.pdf"
            pdf_full=os.path.join(REPORTS_DIR,filename)
            os.makedirs(os.path.dirname(pdf_full),exist_ok=True)
            c=canvas.Canvas(pdf_full,pagesize=letter)

            for (tid,tname), items in groups.items():
                header_pdf(c, f"Monthly Report: {start.strftime('%B %Y')} — {tname}")
                y=9.1*inch
                c.setFont("Helvetica-Bold",10)
                c.drawString(0.8*inch,y,"Date"); c.drawString(1.6*inch,y,"Type"); c.drawString(2.5*inch,y,"Category")
                c.drawString(4.0*inch,y,"Driver"); c.drawRightString(7.7*inch,y,"Amount")
                y-=0.15*inch; c.setFont("Helvetica",10)
                total_inc=0.0; total_exp=0.0
                for r in items:
                    if y<1.1*inch:
                        c.showPage(); header_pdf(c, f"Monthly Report: {start.strftime('%B %Y')} — {tname}")
                        y=9.1*inch
                        c.setFont("Helvetica-Bold",10)
                        c.drawString(0.8*inch,y,"Date"); c.drawString(1.6*inch,y,"Type"); c.drawString(2.5*inch,y,"Category")
                        c.drawString(4.0*inch,y,"Driver"); c.drawRightString(7.7*inch,y,"Amount")
                        y-=0.15*inch; c.setFont("Helvetica",10)

                    amt = r['amount'] if r['is_income']==1 else amount_with_hst(r['amount'], r['hst_included']==1)
                    c.drawString(0.8*inch,y,r['entry_date'])
                    c.drawString(1.6*inch,y,"Income" if r['is_income']==1 else "Expense")
                    c.drawString(2.5*inch,y,r['category'] or "-")
                    c.drawString(4.0*inch,y,r['driver_name'] or "-")
                    c.drawRightString(7.7*inch,y,f"${amt:,.2f}")
                    if r['is_income']==1: total_inc+=amt
                    else: total_exp+=amt
                    y-=0.15*inch

                y-=0.1*inch; c.setFont("Helvetica-Bold",11)
                c.drawRightString(6.9*inch,y,"Total Income:"); c.drawRightString(7.7*inch,y,f"${total_inc:,.2f}")
                y-=0.18*inch; c.drawRightString(6.9*inch,y,"Total Expenses:"); c.drawRightString(7.7*inch,y,f"${total_exp:,.2f}")
                y-=0.18*inch; net=round(total_inc-total_exp,2)
                c.setFillColor(colors.green if net>=0 else colors.red)
                c.drawRightString(6.9*inch,y,"Profit/Loss:"); c.drawRightString(7.7*inch,y,f"${net:,.2f}")
                c.setFillColor(colors.black)
                c.showPage()

            # summary page
            inc,exp,prof = totals("date(entry_date)>=? AND date(entry_date)<?", (str(start),str(end)))
            header_pdf(c, f"Monthly Summary: {start.strftime('%B %Y')} — All Trucks")
            y=9.1*inch
            c.setFont("Helvetica-Bold",11)
            c.drawRightString(6.9*inch,y,"Total Income:"); c.drawRightString(7.7*inch,y,f"${inc:,.2f}")
            y-=0.18*inch; c.drawRightString(6.9*inch,y,"Total Expenses:"); c.drawRightString(7.7*inch,y,f"${exp:,.2f}")
            y-=0.18*inch; c.setFillColor(colors.green if prof>=0 else colors.red)
            c.drawRightString(6.9*inch,y,"Profit/Loss:"); c.drawRightString(7.7*inch,y,f"${prof:,.2f}")
            c.setFillColor(colors.black)
            c.showPage(); c.save()
            pdf_path=pdf_full
        else:
            cur.execute("""SELECT e.*, t.name AS truck_name, d.name AS driver_name
                            FROM entries e
                            LEFT JOIN trucks t ON e.truck_id=t.id
                            LEFT JOIN drivers d ON e.driver_id=d.id
                            WHERE date(entry_date)>=? AND date(entry_date)<? AND truck_id=?
                            ORDER BY date(entry_date) ASC, id ASC""",(str(start),str(end),truck_id))
            rows=cur.fetchall()
            if not rows:
                flash("No data available for the selected month/truck.","warning")
                conn.close()
                return render_template('monthly_reports.html', title=APP_TITLE, trucks=trucks, pdf_path=None)

            inc,exp,prof = totals("date(entry_date)>=? AND date(entry_date)<? AND truck_id=?", (str(start),str(end),truck_id))
            filename=f"Monthly_Report_{start.strftime('%Y_%m')}_Truck_{rows[0]['truck_name']}.pdf"
            pdf_full=os.path.join(REPORTS_DIR,filename)
            os.makedirs(os.path.dirname(pdf_full),exist_ok=True)
            c=canvas.Canvas(pdf_full,pagesize=letter)
            header_pdf(c, f"Monthly Report: {start.strftime('%B %Y')} — {rows[0]['truck_name']}")
            y=9.1*inch
            c.setFont("Helvetica-Bold",10)
            c.drawString(0.8*inch,y,"Date"); c.drawString(1.6*inch,y,"Type"); c.drawString(2.5*inch,y,"Category")
            c.drawString(4.0*inch,y,"Driver"); c.drawRightString(7.7*inch,y,"Amount")
            y-=0.15*inch; c.setFont("Helvetica",10)
            for r in rows:
                if y<1.1*inch:
                    c.showPage(); header_pdf(c, f"Monthly Report: {start.strftime('%B %Y')} — {rows[0]['truck_name']}"); y=9.1*inch
                    c.setFont("Helvetica-Bold",10)
                    c.drawString(0.8*inch,y,"Date"); c.drawString(1.6*inch,y,"Type"); c.drawString(2.5*inch,y,"Category")
                    c.drawString(4.0*inch,y,"Driver"); c.drawRightString(7.7*inch,y,"Amount")
                    y-=0.15*inch; c.setFont("Helvetica",10)
                amt = r['amount'] if r['is_income']==1 else amount_with_hst(r['amount'], r['hst_included']==1)
                c.drawString(0.8*inch,y,r['entry_date'])
                c.drawString(1.6*inch,y,"Income" if r['is_income']==1 else "Expense")
                c.drawString(2.5*inch,y,r['category'] or "-")
                c.drawString(4.0*inch,y,r['driver_name'] or "-")
                c.drawRightString(7.7*inch,y,f"${amt:,.2f}")
                y-=0.15*inch
            y-=0.1*inch; c.setFont("Helvetica-Bold",11)
            c.drawRightString(6.9*inch,y,"Total Income:"); c.drawRightString(7.7*inch,y,f"${inc:,.2f}")
            y-=0.18*inch; c.drawRightString(6.9*inch,y,"Total Expenses:"); c.drawRightString(7.7*inch,y,f"${exp:,.2f}")
            y-=0.18*inch; c.setFillColor(colors.green if (inc-exp)>=0 else colors.red)
            c.drawRightString(6.9*inch,y,"Profit/Loss:"); c.drawRightString(7.7*inch,y,f"${(inc-exp):,.2f}")
            c.setFillColor(colors.black); c.showPage(); c.save()
            pdf_path=pdf_full
    conn.close()
    return render_template('monthly_reports.html', title=APP_TITLE, trucks=trucks, pdf_path=pdf_path)

@app.route('/driver_pay', methods=['GET','POST'])
def driver_pay():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT * FROM drivers ORDER BY name")
    drivers=cur.fetchall()
    items=[]; pdf_path=None
    if request.method=='POST':
        driver_id=request.form.get('driver_id')
        date_from=request.form.get('date_from')
        date_to=request.form.get('date_to')
        where = "is_income=0 AND category='Driver Pay' AND date(entry_date)>=? AND date(entry_date)<=?"
        params=[date_from,date_to]
        if driver_id and driver_id!='all':
            where += " AND driver_id=?"
            params.append(driver_id)
        cur.execute(f"""SELECT e.*, t.name AS truck_name, d.name AS driver_name
                        FROM entries e
                        LEFT JOIN trucks t ON e.truck_id=t.id
                        LEFT JOIN drivers d ON e.driver_id=d.id
                        WHERE {where}
                        ORDER BY date(entry_date) ASC, id ASC""", params)
        items=cur.fetchall()
        if not items:
            flash("No data available for that date range/driver.","warning")
            conn.close()
            return render_template('driver_pay.html', title=APP_TITLE, drivers=drivers, items=[], pdf_path=None)
        total=0.0
        for r in items:
            total += amount_with_hst(r['amount'], r['hst_included']==1)
        dname="All Drivers"
        if driver_id and driver_id!='all':
            cur.execute("SELECT name FROM drivers WHERE id=?",(driver_id,))
            rw=cur.fetchone()
            dname=rw['name'] if rw else "Driver"
        title=f"Driver Pay: {dname} — {date_from} to {date_to}"
        filename=f"Driver_Pay_{dname.replace(' ','_')}_{date_from}_to_{date_to}.pdf"
        pdf_full=os.path.join(REPORTS_DIR,filename)
        os.makedirs(os.path.dirname(pdf_full),exist_ok=True)
        c=canvas.Canvas(pdf_full,pagesize=letter)
        header_pdf(c,title)
        y=9.1*inch
        c.setFont("Helvetica-Bold",10)
        c.drawString(0.8*inch,y,"Date"); c.drawString(2.0*inch,y,"Driver"); c.drawString(4.0*inch,y,"Truck"); c.drawRightString(7.7*inch,y,"Amount")
        y-=0.15*inch; c.setFont("Helvetica",10)
        for r in items:
            if y<1.1*inch:
                c.showPage(); header_pdf(c,title); y=9.1*inch
                c.setFont("Helvetica-Bold",10)
                c.drawString(0.8*inch,y,"Date"); c.drawString(2.0*inch,y,"Driver"); c.drawString(4.0*inch,y,"Truck"); c.drawRightString(7.7*inch,y,"Amount")
                y-=0.15*inch; c.setFont("Helvetica",10)
            amt=amount_with_hst(r['amount'], r['hst_included']==1)
            c.drawString(0.8*inch,y,r['entry_date'])
            c.drawString(2.0*inch,y,r['driver_name'] or "-")
            c.drawString(4.0*inch,y,r['truck_name'] or "-")
            c.drawRightString(7.7*inch,y,f"${amt:,.2f}")
            y-=0.15*inch
        y-=0.1*inch; c.setFont("Helvetica-Bold",12)
        c.drawRightString(6.9*inch,y,"Total Pay:"); c.drawRightString(7.7*inch,y,f"${total:,.2f}")
        c.showPage(); c.save()
        pdf_path=pdf_full
    conn.close()
    return render_template('driver_pay.html', title=APP_TITLE, drivers=drivers, items=items, pdf_path=pdf_path)

@app.route('/download_report')
def download_report():
    fname=request.args.get('fname','')
    if not os.path.isabs(fname):
        path=os.path.join(REPORTS_DIR,fname)
    else:
        path=fname
    path=os.path.realpath(path)
    if not path.startswith(os.path.realpath(REPORTS_DIR)) or not os.path.exists(path):
        flash("Report not found.","warning")
        return redirect(url_for('monthly_reports'))
    return send_file(path, as_attachment=True)

def _ensure_dirs():
    os.makedirs(REPORTS_DIR,exist_ok=True)

if __name__=="__main__":
    init_db(); _ensure_dirs()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=False)
else:
    init_db(); _ensure_dirs()
