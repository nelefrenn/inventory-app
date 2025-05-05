from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from datetime import datetime
import csv

app = Flask(__name__)
app.secret_key = 'secure-key'

# CSV paths
KIT_CSV = 'kit.csv'
INVENTORY_CSV = 'inventory.csv'
USERS_CSV = 'users.csv'
ADMIN_LOGS_CSV = 'admin_logs.csv'
PRODUCTION_LOG_CSV = 'production_log.csv'

# --- Helper functions ---
def load_users():
    return pd.read_csv(USERS_CSV)

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

@app.route('/receiving', methods=['GET', 'POST'])
def receiving():
    if 'user' not in session or session['user']['role'] not in ['daily', 'admin']:
        flash("Access denied.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'start':
            session['start_time'] = datetime.now().isoformat()
            flash("Receiving started.")

        elif action == 'stop':
            start_time = session.pop('start_time', None)
            if start_time:
                stop_time = datetime.now()
                start_dt = datetime.fromisoformat(start_time)
                hours_worked = round((stop_time - start_dt).total_seconds() / 3600, 2)

                user = session['user']
                po_number = request.form.get('po_number', 'Unknown')
                log_entry = [
                    datetime.now().date(),
                    user['first'],
                    user['second'],
                    'Receiving',
                    po_number,
                    hours_worked
                ]

                if not os.path.exists(PRODUCTION_LOG_CSV):
                    with open(PRODUCTION_LOG_CSV, 'w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Date', 'First Name', 'Second Name', 'Activity', 'PO Number', 'Hours Worked'])

                with open(PRODUCTION_LOG_CSV, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(log_entry)

            flash("Session ended. Work logged.")
            session.clear()
            return redirect(url_for('login'))

        elif action == 'close':
            flash("PO closed.")

    return render_template('receiving.html')

@app.route('/testing')
def testing():
    if 'user' not in session or session['user']['role'] not in ['daily', 'admin']:
        flash("Access denied.")
        return redirect(url_for('login'))
    return render_template('testing.html')

@app.route('/inventory')
def inventory():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))
    return render_template('inventory.html')

@app.route('/sell')
def sell():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))
    return render_template('sell.html')

@app.route('/reports')
def reports():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))
    return render_template('reports.html', daily_data=[], weekly_data=[], comparison_data=[])

@app.route('/admin_logs')
def admin_logs():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied. Admins only.")
        return redirect(url_for('login'))
    logs = read_admin_logs()
    return render_template('admin_logs.html', logs=logs.to_dict(orient='records'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
