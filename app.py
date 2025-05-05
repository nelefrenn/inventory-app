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

@app.route('/testing', methods=['GET', 'POST'])
def testing():
    if 'user' not in session or session['user']['role'] not in ['daily', 'admin']:
        flash("Access denied.")
        return redirect(url_for('login'))

    po_number = None
    po_data = []

    if request.method == 'POST':
        if 'load_po' in request.form:
            po_number = request.form['po_number']
            session['po_number'] = po_number
            if os.path.exists(RECEIVING_TEMP_CSV):
                df = pd.read_csv(RECEIVING_TEMP_CSV)
                filtered = df[df['PO Number'] == po_number]
                grouped = filtered.groupby('Product ID').sum().reset_index()
                for _, row in grouped.iterrows():
                    po_data.append({
                        'Product ID': row['Product ID'],
                        'Received': row['Quantity']
                    })
        elif 'start' in request.form:
            session['start_time'] = datetime.now().isoformat()
            flash("Testing started.")
            po_number = session.get('po_number')
            if os.path.exists(RECEIVING_TEMP_CSV):
                df = pd.read_csv(RECEIVING_TEMP_CSV)
                filtered = df[df['PO Number'] == po_number]
                grouped = filtered.groupby('Product ID').sum().reset_index()
                for _, row in grouped.iterrows():
                    po_data.append({
                        'Product ID': row['Product ID'],
                        'Received': row['Quantity']
                    })
        elif 'stop' in request.form:
            start_time = session.pop('start_time', None)
            po_number = session.get('po_number', 'Unknown')
            if start_time:
                stop_time = datetime.now()
                start_dt = datetime.fromisoformat(start_time)
                hours_worked = round((stop_time - start_dt).total_seconds() / 3600, 2)
                user = session['user']
                log_entry = [
                    datetime.now().date(),
                    user['first'],
                    user['second'],
                    'Testing',
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

                # Descontar productos fallidos y registrar log
                total_rows = int(request.form['total_rows'])
                inventory_df = pd.read_csv(INVENTORY_CSV)
                testing_log = []
                for i in range(1, total_rows + 1):
                    product_id = request.form.get(f'product_id_{i}')
                    failed = int(request.form.get(f'failed_{i}', 0))
                    tested = int(request.form.get(f'tested_{i}', 0))
                    good = tested - failed if tested >= failed else 0

                    testing_log.append([
                        datetime.now().date(), po_number, user['first'], user['second'],
                        product_id, tested, good, failed
                    ])

                    if product_id in inventory_df['Product ID'].values:
                        inventory_df.loc[inventory_df['Product ID'] == product_id, 'Quantity'] -= failed

                inventory_df.to_csv(INVENTORY_CSV, index=False)

                if not os.path.exists(TESTING_LOG_CSV):
                    with open(TESTING_LOG_CSV, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Date', 'PO Number', 'First Name', 'Second Name', 'Product ID', 'Tested', 'Good', 'Failed'])
                with open(TESTING_LOG_CSV, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(testing_log)

            flash("Session ended. Work logged. Inventory updated.")
            session.clear()
            return redirect(url_for('login'))
        elif 'close' in request.form:
            flash("PO closed.")
            session.pop('po_number', None)

    return render_template('testing.html', po_data=po_data, po_number=po_number)

# ... El resto de rutas como receiving, sell, inventory, reports, admin_logs iría después ...
