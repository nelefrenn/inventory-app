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

def load_inventory():
    return pd.read_csv(INVENTORY_CSV)

def save_inventory(df):
    df.to_csv(INVENTORY_CSV, index=False)

def load_receiving_temp():
    if os.path.exists(RECEIVING_TEMP_CSV):
        return pd.read_csv(RECEIVING_TEMP_CSV)
    return pd.DataFrame(columns=['PO Number', 'Product ID', 'Quantity'])

def save_receiving_temp(df):
    df.to_csv(RECEIVING_TEMP_CSV, index=False)

def clear_receiving_temp():
    if os.path.exists(RECEIVING_TEMP_CSV):
        os.remove(RECEIVING_TEMP_CSV)

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
    if 'user' not in session:
        return redirect(url_for('login'))

    inventory_df = load_inventory()
    po_number = None
    current_po = load_receiving_temp()

    if request.method == 'POST':
        if 'new_po' in request.form or 'continue_po' in request.form:
            po_number = request.form['po_number']
        elif 'add_product' in request.form:
            po_number = request.form['po_number']
            product_id = request.form['product_id']
            quantity = int(request.form['quantity'])
            new_row = pd.DataFrame([[po_number, product_id, quantity]], columns=['PO Number', 'Product ID', 'Quantity'])
            current_po = pd.concat([current_po, new_row], ignore_index=True)
            save_receiving_temp(current_po)
        elif 'start' in request.form:
            session['start_time'] = datetime.now().isoformat()
        elif 'stop' in request.form:
            if not current_po.empty:
                for _, row in current_po.iterrows():
                    inventory_df.loc[inventory_df['Product ID'] == row['Product ID'], 'Qty'] += row['Quantity']
                save_inventory(inventory_df)
                duration = 0
                if 'start_time' in session:
                    start_time = datetime.fromisoformat(session['start_time'])
                    duration = (datetime.now() - start_time).total_seconds() / 3600
                with open(PRODUCTION_LOG_CSV, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([datetime.now().date(), session['user']['first'], session['user']['second'], 'Receiving', po_number, round(duration, 2)])
                flash("Progress saved. You can continue later.")
                return redirect(url_for('logout'))
        elif 'close' in request.form:
            flash("PO has been marked as closed. You will not be able to edit it again.")
            clear_receiving_temp()
            return redirect(url_for('daily'))

    return render_template('receiving.html', inventory=inventory_df['Product ID'].tolist(), po_active=not current_po.empty, current_po=current_po.to_dict(orient='records'), po_number=po_number)

@app.route('/testing_report')
def testing_report():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    if not os.path.exists(TESTING_LOG_CSV):
        return render_template('testing_report.html', data=[])

    df = pd.read_csv(TESTING_LOG_CSV, names=[
        'Date', 'First Name', 'Second Name', 'PO Number',
        'Product ID', 'Tested', 'Failed', 'Good'
    ])

    po_filter = request.args.get('po_number', '').strip()
    product_filter = request.args.get('product_id', '').strip()
    operator_filter = request.args.get('operator', '').strip().lower()

    if po_filter:
        df = df[df['PO Number'].astype(str).str.contains(po_filter, case=False)]
    if product_filter:
        df = df[df['Product ID'].astype(str).str.contains(product_filter, case=False)]
    if operator_filter:
        df = df[df['First Name'].str.lower().str.contains(operator_filter) |
                df['Second Name'].str.lower().str.contains(operator_filter)]

    return render_template('testing_report.html', data=df.to_dict(orient='records'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

