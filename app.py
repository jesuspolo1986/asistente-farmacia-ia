import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)
# Memoria de trabajo
inventario = {"df": None, "tasa": 55.40}

def limpiar_pregunta(texto):
    texto = texto.lower()
    frases = ["cuanto cuesta", "dame el precio de", "reporte de", "estatus de", "analisis de", "precio del"]
    for f in frases: texto = texto.replace(f, "")
    return texto.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: return "Elena: Por favor, sincronice el inventario primero."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    pregunta_limpia = pregunta_original.lower()
    df = inventario["df"]
    hoy = datetime.now()

    # ==========================================================
    # LÓGICA DE COMANDOS GLOBALES (SOLO ADMIN)
    # ==========================================================
    if modo_admin:
        # 1. Comando para VENCIDOS
        if "vencido" in pregunta_limpia or "vencidos" in pregunta_limpia:
            vencidos_df = df[pd.to_datetime(df['Vencimiento']) < hoy]
            if vencidos_df.empty: return "Excelente, no hay productos vencidos en sistema."
            lista = ", ".join(vencidos_df['Producto'].tolist())
            return f"Alerta de Auditoría: Tenemos vencidos: {lista}. Revise el PDF para ubicarlos."

        # 2. Comando para FALTANTES / STOCK BAJO
        if any(palabra in pregunta_limpia for palabra in ["falta", "stock bajo", "reposición", "comprar"]):
            faltantes_df = df[df['Stock Actual'] <= df['Stock Mínimo']]
            if faltantes_df.empty: return "El inventario está completo según los niveles mínimos."
            # Tomamos los 5 más críticos para no saturar el audio
            lista_f = ", ".join(faltantes_df['Producto'].head(5).tolist())
            return f"Atención: Faltan {len(faltantes_df)} productos. Los más urgentes son: {lista_f}. He preparado la lista completa en el botón de PDF."

    # ==========================================================
    # BÚSQUEDA INDIVIDUAL (LÓGICA ANTERIOR)
    # ==========================================================
    producto_buscado = limpiar_pregunta(pregunta_original)
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        costo_usd = float(fila['Costo'])
        stock = int(fila['Stock Actual'])
        minimo = int(fila['Stock Mínimo'])

        # Pareto e Indicadores
        df['Valor_Inv'] = df['Stock Actual'] * df['Precio Venta']
        umbral_pareto = df['Valor_Inv'].quantile(0.8)
        es_pareto = "⭐ PARETO A" if (stock * precio_usd) >= umbral_pareto else "Clase B/C"
        vencido = datetime.strptime(str(fila['Vencimiento']), '%Y-%m-%d') < hoy
        margen = ((precio_usd - costo_usd) / precio_usd) * 100

        if not modo_admin:
            if vencido: return f"El producto {match[0]} no está disponible por el momento."
            return f"El valor de {match[0]} es {precio_bs:,.2f} BS ({precio_usd} USD)."
        else:
            rec = "✅ ÓPTIMO"
            if vencido: rec = "❌ VENCIDO"
            elif stock <= minimo: rec = "⚠️ REPONER"
            elif stock > (minimo * 3): rec = "📦 SOBRE-STOCK"
            return f"AUDITORÍA: {match[0]} ({es_pareto}). Margen: {margen:.1f}%. Stock: {stock}. Predicción: {rec}"
    
    return "Elena: No logré identificar el producto o comando."

@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario Sincronizado."})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 55.4), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error", 400
    df = inventario["df"]
    hoy = datetime.now()
    faltantes = df[df['Stock Actual'] <= df['Stock Mínimo']]
    vencidos = df[pd.to_datetime(df['Vencimiento']) < hoy]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE GERENCIA - ELENA AI", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Fecha: {hoy.strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "PRODUCTOS PARA REPOSICIÓN", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, f in faltantes.iterrows():
        pdf.cell(190, 7, f"- {f['Producto']}: {f['Stock Actual']} unidades (Mín: {f['Stock Mínimo']})", ln=True)
    
    pdf.ln(5)
    pdf.set_fill_color(255, 200, 200)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "PRODUCTOS VENCIDOS", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, v in vencidos.iterrows():
        pdf.cell(190, 7, f"- {v['Producto']}: Vencido el {v['Vencimiento']}", ln=True)

    output = io.BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Reporte_Cierre.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))