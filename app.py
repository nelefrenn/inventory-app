from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from datetime import datetime
import csv

app = Flask(__name__)
app.secret_key = 'secure-key'

KIT_CSV = 'kit.csv'
INVENTORY_CSV = 'inventory.csv'
USERS_CSV = 'users.csv'
ADMIN_LOGS_CSV = 'admin_logs.csv'
PRODUCTION_LOG_CSV = 'production_log.csv'
RECEIVING_TEMP_CSV = 'receiving_temp.csv'
TESTING_LOG_CSV = 'testing_log.csv'

# --- Helper functions ---
def load_users():
    return pd.read_csv(USERS_CSV, dtype={'Password': str})

def verify_user(first, second, password):
    df = load_users()
    match = df[(df['First Name'] == first) & (df['Second Name'] == second)]
    if not match.empty and match.iloc[0]['Password'] == password:
        return match.iloc[0]['Role']
    return None

def register_user(first, second, password):
    df = load_users()
    mask = (df['First Name'] == first) & (df['Second Name'] == second)
    if not df[mask].empty:
        if pd.isna(df.loc[mask, 'Password'].values[0]) or df.loc[mask, 'Password'].values[0] == '':
            df.loc[mask, 'Password'] = password
            df.to_csv(USERS_CSV, index=False)
            log_admin_action('system', 'Registered user', f'{first} {second}')
            return True
    return False

def log_admin_action(username, action, details):
    with open(ADMIN_LOGS_CSV, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().isoformat(), username, action, details])

def read_admin_logs():
    if os.path.exists(ADMIN_LOGS_CSV):
        return pd.read_csv(ADMIN_LOGS_CSV, names=['Timestamp', 'Username', 'Action', 'Details'])
    return pd.DataFrame(columns=['Timestamp', 'Username', 'Action', 'Details'])

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        first = request.form['firstname']
        second = request.form['secondname']
        password = request.form['password']
        role = verify_user(first, second, password)
        if role:
            session['user'] = {'first': first, 'second': second, 'role': role}
            flash(f"Welcome {first} {second} ({role})")
            return redirect(url_for('daily'))
        else:
            flash("Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first = request.form['firstname']
        second = request.form['secondname']
        password = request.form['password']
        if register_user(first, second, password):
            flash("Registration successful. Please log in.")
            return redirect(url_for('login'))
        else:
            flash("You are not pre-authorized or already registered.")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))

@app.route('/daily')
def daily():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('daily.html')

@app.route('/testing_report')
def testing_report():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    if not os.path.exists(TESTING_LOG_CSV):
        return render_template('testing_report.html', data=[])

    df = pd.read_csv(TESTING_LOG_CSV)

    po_filter = request.args.get('po_number', '').strip()
    product_filter = request.args.get('product_id', '').strip()
    operator_filter = request.args.get('operator', '').strip().lower()

    if po_filter:
        df = df[df['PO Number'].astype(str).str.contains(po_filter, case=False)]
    if product_filter:
        df = df[df['Product ID'].astype(str).str.contains(product_filter, case=False)]
    if operator_filter:
        df = df[df['First Name'].str.lower().str.contains(operator_filter) | df['Second Name'].str.lower().str.contains(operator_filter)]

    return render_template('testing_report.html', data=df.to_dict(orient='records'))

@app.route('/sell')
def sell():
    return render_template('sell.html')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html', data=[])

@app.route('/reports')
def reports():
    return render_template('reports.html', data=[])

@app.route('/admin_logs')
def admin_logs():
    return render_template('admin_logs.html', data=[])

@app.route('/receiving', methods=['GET', 'POST'])
def receiving():
    return render_template('receiving.html')

@app.route('/testing', methods=['GET', 'POST'])
def testing():
    return render_template('testing.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
