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

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('login'))

    inventory_df = load_inventory()

    if request.method == 'POST':
        if 'product' in request.form:
            new_product = {
                'Product ID': request.form['product'],
                'Qty': int(request.form['qty']),
                'Min Qty': int(request.form['min_qty'])
            }
            inventory_df = pd.concat([inventory_df, pd.DataFrame([new_product])], ignore_index=True)
        elif 'update_product' in request.form:
            product_id = request.form['update_product']
            new_qty = int(request.form['update_qty'])
            new_min = request.form.get('update_min')
            inventory_df.loc[inventory_df['Product ID'] == product_id, 'Qty'] = new_qty
            if new_min:
                inventory_df.loc[inventory_df['Product ID'] == product_id, 'Min Qty'] = int(new_min)

        save_inventory(inventory_df)
        flash("Inventory updated successfully.")
        return redirect(url_for('inventory'))

    show_all = request.args.get('all') == '1'
    if not show_all:
        inventory_df = inventory_df[inventory_df['Qty'] < inventory_df['Min Qty']]

    return render_template('inventory.html', inventory=inventory_df.to_dict(orient='records'))

