import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from rapidfuzz import process, utils
from datetime import datetime, timedelta

# Intento de importación segura de Supabase
try:
    from supabase import create_client, Client
    USE_SUPABASE = True
except ImportError:
    USE_SUPABASE = False

app = Flask(__name__)
app.secret_key = 'elena_farmacia_2026_key'

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://kebpamfydhnxeaeegulx.supabase.co"
SUPABASE_KEY = "sb_secret_lSrahuG5Nv32T1ZaV7lfRw_WFXuiP4H" 
ADMIN_PASS = "1234"

if USE_SUPABASE:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        USE_SUPABASE = False

# Memoria global
inventario = {"df": None, "tasa": 54.20}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario', 'precio_usd'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia']
}

@app.route('/')
def home():
    # Tasa fija o scraping según prefieras para estabilidad
    tasa = inventario["tasa"]
    dias_restantes = 30 # Valor por defecto si falla login
    return render_template('index.html', tasa=tasa, dias_restantes=dias_restantes)

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    
    if "activar modo gerencia" in pregunta:
        return jsonify({"respuesta": "Modo gerencia activado.", "status": "MODO_ADMIN_ACTIVADO"})

    if inventario["df"] is None:
        return jsonify({"respuesta": "Por favor, cargue el inventario primero."})
    
    df = inventario["df"]
    # Búsqueda difusa
    match = process.extractOne(pregunta.replace("precio", "").strip(), df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa = inventario["tasa"]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * tasa
        res = f"El {match[0]} cuesta {p_bs:,.2f} bolívares, que equivalen a {p_usd:,.2f} dólares."
        return jsonify({"respuesta": res})

    return jsonify({"respuesta": "Lo siento, no encontré ese producto en el inventario."})

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('archivo')
    if not file: return jsonify({"success": False, "mensaje": "No se recibió el archivo"})
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(stream)
        else:
            df = pd.read_csv(stream)
        
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario cargado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)