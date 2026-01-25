import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, send_file
from rapidfuzz import process, utils
from datetime import datetime, timedelta
from supabase import create_client, Client
from fpdf import FPDF
from pyDolarVenezuela.pages import AlCambio
from pyDolarVenezuela import Monitor

app = Flask(__name__)
app.secret_key = 'elena_farmacia_2026_key'

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://kebpamfydhnxeaeegulx.supabase.co"
SUPABASE_KEY = "sb_secret_lSrahuG5Nv32T1ZaV7lfRw_WFXuiP4H" 
ADMIN_PASS = "1234"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Memoria global (Lógica del código que te funciona)
inventario = {"df": None, "tasa": 54.20}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario', 'precio_usd'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia']
}

def obtener_tasa_real():
    try:
        monitor = Monitor(AlCambio, 'USD')
        monitores = monitor.get_all_monitors()
        for m in monitores:
            if "BCV" in m.title:
                val = float(m.price)
                if 10 < val < 100: return val
        return 54.20
    except: return 54.20

@app.route('/')
def home():
    tasa = obtener_tasa_real()
    inventario["tasa"] = tasa
    dias_restantes = 0
    if session.get('autenticado') and session.get('fecha_vencimiento'):
        try:
            vence = datetime.strptime(session['fecha_vencimiento'], '%Y-%m-%d').date()
            dias_restantes = (vence - datetime.now().date()).days
        except: pass
    return render_template('index.html', tasa=tasa, dias_restantes=dias_restantes)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').lower().strip()
    try:
        res = supabase.table("suscripciones").select("*").eq("email", email).eq("activo", 1).execute()
        if res.data:
            session['autenticado'] = True
            session['usuario'] = email
            session['fecha_vencimiento'] = res.data[0]['fecha_vencimiento']
            return redirect(url_for('home'))
        return "No autorizado", 401
    except: return "Error DB", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    
    if "activar modo gerencia" in pregunta:
        return jsonify({"respuesta": "MODO_ADMIN_ACTIVADO", "modo_admin": True})

    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: Por favor, cargue el inventario en el panel de gerencia."})
    
    df = inventario["df"]
    # Búsqueda difusa (Rapidfuzz)
    match = process.extractOne(pregunta.replace("precio", "").strip(), df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa = inventario["tasa"]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * tasa
        res = f"El {match[0]} cuesta {p_bs:,.2f} Bs, que son {p_usd:,.2f} $."
        return jsonify({"respuesta": res})

    return jsonify({"respuesta": "No encontré ese producto."})

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('archivo') # Nombre 'archivo' para tu HTML
    if not file: return jsonify({"success": False, "mensaje": "Sin archivo"})
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        # Normalizar columnas
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario cargado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- PANEL ADMIN ---
@app.route('/admin')
def admin_panel():
    auth = request.args.get('auth_key')
    if auth != ADMIN_PASS: return "No autorizado", 403
    res = supabase.table("suscripciones").select("*").execute()
    usuarios = res.data
    stats = {"total": len(usuarios), "activos": 0, "vencidos": 0}
    hoy = datetime.now().date()
    for u in usuarios:
        vence = datetime.strptime(u['fecha_vencimiento'], '%Y-%m-%d').date()
        u['vencido'] = vence < hoy
        if u['activo'] == 1: stats["activos"] += 1
        if u['vencido']: stats["vencidos"] += 1
    return render_template('admin.html', usuarios=usuarios, stats=stats, admin_pass=ADMIN_PASS)

@app.route('/admin/renovar/<int:user_id>', methods=['POST'])
def renovar_usuario(user_id):
    nueva_fecha = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    supabase.table("suscripciones").update({"fecha_vencimiento": nueva_fecha, "activo": 1}).eq("id", user_id).execute()
    return redirect(url_for('admin_panel', auth_key=ADMIN_PASS))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))