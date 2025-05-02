from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import os
from io import BytesIO

app = Flask(__name__)

KIT_CSV = 'kit.csv'
INVENTORY_CSV = 'inventory.csv'
EXPORT_XLSX = 'inventory_export.xlsx'

# Leer datos

def read_inventory():
    return pd.read_csv(INVENTORY_CSV)

def read_kits():
    return pd.read_csv(KIT_CSV)

# Guardar nuevo producto al inventario
def add_product_to_inventory(product_id, qty, min_qty):
    inv = read_inventory()
    new_row = pd.DataFrame([[product_id, qty, min_qty]], columns=['Product ID', 'Qty', 'Min Qty'])
    inv = pd.concat([inv, new_row], ignore_index=True)
    inv.to_csv(INVENTORY_CSV, index=False)

# Guardar nuevo kit
def add_new_kit(kit_name, components):
    rows = []
    for comp in components:
        rows.append([kit_name, comp['product'], comp['quantity']])
    new_kit_df = pd.DataFrame(rows, columns=['Product ID', 'Component Product ID', 'Quantity'])
    existing = read_kits()
    updated = pd.concat([existing, new_kit_df], ignore_index=True)
    updated.to_csv(KIT_CSV, index=False)

# Calcular consumo por venta de kits
def consumir_kit(kit_name, cantidad):
    kits = read_kits()
    inv = read_inventory()
    componentes = kits[kits['Product ID'] == kit_name]

    for _, fila in componentes.iterrows():
        comp = fila['Component Product ID']
        q = pd.to_numeric(fila['Quantity'], errors='coerce')
        inv.loc[inv['Product ID'] == comp, 'Qty'] -= q * cantidad

    inv.to_csv(INVENTORY_CSV, index=False)

@app.route('/')
@app.route('/sell', methods=['GET', 'POST'])
def sell():
    kits = read_kits()['Product ID'].unique()
    inventory = read_inventory()
    if request.method == 'POST':
        if 'register_sale' in request.form:
            kit = request.form['kit']
            qty = int(request.form['cantidad'])
            consumir_kit(kit, qty)
            return redirect(url_for('inventory'))
        elif 'create_kit' in request.form:
            kit_name = request.form['kit_name']
            components = []
            for i in range(0, len(request.form.getlist('component'))):
                components.append({
                    'product': request.form.getlist('component')[i],
                    'quantity': float(request.form.getlist('comp_qty')[i])
                })
            add_new_kit(kit_name, components)
            return redirect(url_for('sell'))
    return render_template('sell.html', kits=kits, inventory=inventory)

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    show_all = request.args.get('all') == '1'
    inv = read_inventory()
    if not show_all:
        inv = inv[inv['Qty'] < inv['Min Qty']]

    if request.method == 'POST':
        new_product = request.form['product']
        qty = float(request.form['qty'])
        min_qty = float(request.form['min_qty'])
        add_product_to_inventory(new_product, qty, min_qty)
        return redirect(url_for('inventory'))

    return render_template('inventory.html', inventory=inv.to_dict(orient='records'), show_all=show_all)

@app.route('/export')
def export():
    inv = read_inventory()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        inv.to_excel(writer, index=False, sheet_name='Inventory')
    output.seek(0)
    return send_file(output, download_name=EXPORT_XLSX, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
