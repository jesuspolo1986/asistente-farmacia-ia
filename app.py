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

# --- LÓGICA DE INTELIGENCIA ---
def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: return "Elena: Sincronice el archivo primero."
    
    df = inventario["df"]
    tasa = float(tasa_recibida)
    p_limpia = pregunta_original.lower()
    hoy = datetime.now()

    if modo_admin:
        # 1. Comandos Globales Admin
        if any(x in p_limpia for x in ["vencido", "caducado", "vence", "auditar"]):
            vencidos = df[pd.to_datetime(df['Vencimiento'], errors='coerce') < hoy]
            if vencidos.empty: return "Auditoría: 0 productos vencidos."
            perdida = (vencidos['Stock Actual'] * vencidos['Costo']).sum()
            return f"🚨 [ADMIN] {len(vencidos)} vencidos. Pérdida total: ${perdida:,.2f} USD."

        # 2. Búsqueda de producto con MARGEN
        prod_buscado = limpiar_pregunta(pregunta_original)
        match = process.extractOne(prod_buscado, df['Producto'].astype(str).tolist(), processor=utils.default_process)
        
        if match and match[1] > 60:
            f = df[df['Producto'] == match[0]].iloc[0]
            margen = ((f['Precio Venta'] - f['Costo']) / f['Precio Venta']) * 100
            return (f"📊 [AUDITORÍA] {match[0]}\n"
                    f"Costo: ${f['Costo']:.2f} | Venta: ${f['Precio Venta']:.2f}\n"
                    f"Margen: {margen:.1f}% | Stock: {f['Stock Actual']}")

    # MODO USUARIO (Solo precios)
    prod_buscado = limpiar_pregunta(pregunta_original)
    match = process.extractOne(prod_buscado, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        return f"El {match[0]} cuesta {f['Precio Venta']*tasa:,.2f} BS (${f['Precio Venta']:,.2f} USD)."

    return "Producto no encontrado."

def limpiar_pregunta(t):
    for f in ["precio", "cuanto cuesta", "dame el"]: t = t.lower().replace(f, "")
    return t.strip()

# --- RUTAS ---
@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        # Mapeo
        nuevas = {}
        for est, sin in MAPEO_COLUMNAS.items():
            for c in df.columns:
                if str(c).lower().strip() in sin: nuevas[c] = est
        df.rename(columns=nuevas, inplace=True)
        
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario Farmacia Sincronizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error", 400
    df = inventario["df"]
    modo_admin = request.args.get('admin') == 'true'
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, f"REPORTE DE FARMACIA - {'MODO AUDITOR' if modo_admin else 'CATÁLOGO'}", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 10)
    pdf.ln(5)
    # Encabezados
    headers = ["Producto", "Precio (USD)", "Stock"]
    if modo_admin: headers += ["Costo", "Margen %"]
    
    for h in headers: pdf.cell(38 if modo_admin else 63, 10, h, 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 9)
    for _, fila in df.iterrows():
        pdf.cell(38 if modo_admin else 63, 10, str(fila['Producto'])[:20], 1)
        pdf.cell(38 if modo_admin else 63, 10, f"${fila['Precio Venta']:.2f}", 1)
        pdf.cell(38 if modo_admin else 63, 10, str(fila['Stock Actual']), 1)
        if modo_admin:
            m = ((fila['Precio Venta'] - fila['Costo']) / fila['Precio Venta']) * 100
            pdf.cell(38, 10, f"${fila['Costo']:.2f}", 1)
            pdf.cell(38, 10, f"{m:.1f}%", 1)
        pdf.ln()

    output = io.BytesIO()
    pdf_string = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_string)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Reporte_Farmacia.pdf")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))