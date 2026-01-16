import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)

# --- MEMORIA DE TRABAJO ---
# Se mantiene global para que todas las terminales consulten el mismo inventario
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

# --- LÓGICA DE INTELIGENCIA (Sin cambios para no afectar funcionamiento) ---
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
            # Cálculo de margen
            if 'Costo' in f and f['Precio Venta'] > 0:
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

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def index(): 
    # Terminal de Ventas: Carga el Aura azul por defecto
    return render_template('index.html', tasa=inventario["tasa"], modo_inicial="vendedor")

@app.route('/gerencia')
def gerencia(): 
    # Terminal de Oficina: Carga el Aura púrpura y funciones admin
    return render_template('index.html', tasa=inventario["tasa"], modo_inicial="admin")

# --- RUTAS DE API ---

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
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
    # Se recibe el 'modo_admin' desde el frontend (Aura púrpura o azul)
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error: No hay inventario cargado", 400
    
    df = inventario["df"]
    modo_admin = request.args.get('admin') == 'true'
    hoy = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 15, f"REPORTE: {'AUDITORÍA INTERNA' if modo_admin else 'CATÁLOGO DE PRECIOS'}", ln=True, align='C')
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Fecha: {hoy}", ln=True, align='C')
    pdf.ln(5)

    if modo_admin:
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 10, " RESUMEN FINANCIERO", 1, ln=True, fill=True)
        inv_total = (df['Stock Actual'] * df['Costo']).sum()
        venta_total = (df['Stock Actual'] * df['Precio Venta']).sum()
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 10, f" Inversión: ${inv_total:,.2f}", 1)
        pdf.cell(95, 10, f" Proyección: ${venta_total:,.2f}", 1, ln=True)
        pdf.ln(5)

    # Configuración de tabla según el modo
    col_pro = 80 if modo_admin else 110
    col_pre = 35 if modo_admin else 40
    col_sto = 25 if modo_admin else 40
    
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_pro, 10, " Producto", 1, 0, 'L', True)
    pdf.cell(col_pre, 10, " Precio", 1, 0, 'C', True)
    pdf.cell(col_sto, 10, " Stock", 1, 0, 'C', True)
    if modo_admin:
        pdf.cell(25, 10, " Costo", 1, 0, 'C', True)
        pdf.cell(25, 10, " Margen", 1, 0, 'C', True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    for _, fila in df.iterrows():
        pdf.cell(col_pro, 8, f" {str(fila['Producto'])[:30]}", 1)
        pdf.cell(col_pre, 8, f"${fila['Precio Venta']:,.2f}", 1, 0, 'C')
        pdf.cell(col_sto, 8, str(int(fila['Stock Actual'])), 1, 0, 'C')
        if modo_admin:
            m = ((fila['Precio Venta'] - fila['Costo']) / fila['Precio Venta']) * 100 if fila['Precio Venta'] > 0 else 0
            pdf.cell(25, 8, f"${fila['Costo']:.2f}", 1, 0, 'C')
            pdf.cell(25, 8, f"{m:.1f}%", 1, 0, 'C')
        pdf.ln()

    output = io.BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Reporte_Elena.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))