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

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    kits_df = pd.read_csv(KIT_CSV)
    inventory_df = pd.read_csv(INVENTORY_CSV)

    if request.method == 'POST':
        if 'register_sale' in request.form:
            kit_name = request.form['kit']
            quantity = int(request.form['quantity'])
            kit_components = kits_df[kits_df['Kit Name'] == kit_name]
            for _, row in kit_components.iterrows():
                inventory_df.loc[inventory_df['Product ID'] == row['Product ID'], 'Qty'] -= row['Quantity'] * quantity
            inventory_df.to_csv(INVENTORY_CSV, index=False)
            flash(f"{quantity} units of {kit_name} sold and inventory updated.")
        elif 'create_kit' in request.form:
            kit_name = request.form['kit_name']
            components = request.form.getlist('component[]')
            quantities = request.form.getlist('comp_qty[]')
            new_rows = []
            for comp, qty in zip(components, quantities):
                new_rows.append({'Kit Name': kit_name, 'Product ID': comp, 'Quantity': int(qty)})
            new_df = pd.DataFrame(new_rows)
            kits_df = pd.concat([kits_df, new_df], ignore_index=True)
            kits_df.to_csv(KIT_CSV, index=False)
            flash(f"Kit '{kit_name}' created successfully.")

    kits = kits_df['Kit Name'].unique().tolist()
    return render_template('sell.html', kits=kits, inventory=inventory_df['Product ID'].tolist())

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    df = load_inventory()

    if request.method == 'POST':
        if 'product' in request.form:
            new_row = pd.DataFrame([{
                'Product ID': request.form['product'],
                'Qty': int(request.form['qty']),
                'Min Qty': int(request.form['min_qty'])
            }])
            df = pd.concat([df, new_row], ignore_index=True)
        elif 'update_product' in request.form:
            product = request.form['update_product']
            new_qty = int(request.form['update_qty'])
            new_min = request.form.get('update_min')
            df.loc[df['Product ID'] == product, 'Qty'] = new_qty
            if new_min:
                df.loc[df['Product ID'] == product, 'Min Qty'] = int(new_min)
        save_inventory(df)

    show_all = request.args.get('all') == '1'
    if not show_all:
        df = df[df['Qty'] < df['Min Qty']]

    return render_template('inventory.html', inventory=df.to_dict(orient='records'))

@app.route('/reports')
def reports():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    if not os.path.exists(PRODUCTION_LOG_CSV):
        return render_template('reports.html', data=[])

    df = pd.read_csv(PRODUCTION_LOG_CSV, names=["Date", "First Name", "Second Name", "Activity", "PO Number", "Hours Worked"])
    return render_template('reports.html', data=df.to_dict(orient='records'))

@app.route('/admin_logs')
def admin_logs():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    df = read_admin_logs()
    return render_template('admin_logs.html', data=df.to_dict(orient='records'))

# Asegúrate de que /receiving y /testing también estén aquí...
# (omitidos en este fragmento por claridad si ya están implementados)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

