from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
import os
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secure-key'  # Change in production

# CSV paths
KIT_CSV = 'kit.csv'
INVENTORY_CSV = 'inventory.csv'
USERS_CSV = 'users.csv'

# --- Helper Functions ---
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
            return True
    return False

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
            if role == 'admin':
                return redirect(url_for('inventory'))
            else:
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

@app.route('/daily')
def daily():
    if 'user' not in session:
        return redirect(url_for('login'))
    if session['user']['role'] not in ['daily', 'admin']:
        return redirect(url_for('login'))
    return render_template('daily.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))

# Placeholder routes to connect UI
@app.route('/receiving')
def receiving():
    return render_template('receiving.html')

@app.route('/testing')
def testing():
    return render_template('testing.html')

@app.route('/reports')
def reports():
    return render_template('reports.html', daily_data=[], weekly_data=[], comparison_data=[])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

