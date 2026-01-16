import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)

# --- MEMORIA DE TRABAJO ---
inventario = {"df": None, "tasa": 325.40, "rubro": "Farmacia"}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia'],
    'Stock Mínimo': ['stock mínimo', 'minimo', 'reorden'],
    'Vencimiento': ['vencimiento', 'vence', 'expiracion'],
    'Ubicación': ['ubicación', 'estante', 'pasillo', 'deposito']
}

def limpiar_pregunta(t):
    for f in ["precio", "cuanto cuesta", "dame el", "dime el"]: t = t.lower().replace(f, "")
    return t.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: return "Elena: Sincronice el archivo primero."
    
    df = inventario["df"]
    tasa = float(tasa_recibida)
    p_limpia = pregunta_original.lower()
    hoy = datetime.now()

    if modo_admin:
        if any(x in p_limpia for x in ["vencido", "caducado", "vence", "auditar"]):
            vencidos = df[pd.to_datetime(df['Vencimiento'], errors='coerce') < hoy]
            if vencidos.empty: return "Auditoría: 0 productos vencidos."
            perdida = (vencidos['Stock Actual'] * vencidos['Costo']).sum()
            return f"🚨 [ADMIN] {len(vencidos)} vencidos. Pérdida total: ${perdida:,.2f} USD."

        prod_buscado = limpiar_pregunta(pregunta_original)
        match = process.extractOne(prod_buscado, df['Producto'].astype(str).tolist(), processor=utils.default_process)
        if match and match[1] > 60:
            f = df[df['Producto'] == match[0]].iloc[0]
            m = ((f['Precio Venta'] - f['Costo']) / f['Precio Venta']) * 100 if f['Precio Venta'] > 0 else 0
            return (f"📊 [AUDITORÍA] {match[0]}\n"
                    f"Costo: ${f['Costo']:.2f} | Venta: ${f['Precio Venta']:.2f}\n"
                    f"Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}")

    prod_buscado = limpiar_pregunta(pregunta_original)
    match = process.extractOne(prod_buscado, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        return f"El {match[0]} cuesta {f['Precio Venta']*tasa:,.2f} BS (${f['Precio Venta']:,.2f} USD)."

    return "Producto no encontrado."

@app.route('/', methods=['GET'])
def index(): 
    return render_template('index.html', tasa=inventario["tasa"], modo_inicial="vendedor")

@app.route('/gerencia', methods=['GET'])
def gerencia(): 
    return render_template('index.html', tasa=inventario["tasa"], modo_inicial="admin")

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario Sincronizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)