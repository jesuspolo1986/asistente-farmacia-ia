import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)
# Memoria temporal para el inventario y la tasa
inventario = {"df": None, "tasa": 55.40}

def limpiar_pregunta(texto):
    texto = texto.lower()
    # Limpiamos frases comunes para que el buscador se enfoque en el producto
    frases = ["cuanto cuesta", "dame el precio de", "reporte de", "estatus de", "analisis de", "precio del"]
    for f in frases: texto = texto.replace(f, "")
    return texto.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: return "Elena: Por favor, cargue la base de datos primero."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    producto_buscado = limpiar_pregunta(pregunta_original)
    
    df = inventario["df"]
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        costo_usd = float(fila['Costo'])
        stock = int(fila['Stock Actual'])
        minimo = int(fila['Stock Mínimo'])

        # --- LÓGICA DE PARETO ---
        df['Valor_Inv'] = df['Stock Actual'] * df['Precio Venta']
        umbral_pareto = df['Valor_Inv'].quantile(0.8)
        es_pareto = "⭐ PARETO A" if (stock * precio_usd) >= umbral_pareto else "Clase B/C"

        # --- LÓGICA DE VENCIMIENTO ---
        venc_str = str(fila['Vencimiento'])
        vencido = datetime.strptime(venc_str, '%Y-%m-%d') < datetime.now()
        margen = ((precio_usd - costo_usd) / precio_usd) * 100

        if not modo_admin:
            if vencido: return f"El activo {match[0]} no está disponible por seguridad."
            return f"El valor de {match[0]} es {precio_bs:,.2f} BS ({precio_usd} USD)."
        
        else:
            # PREDICCIONES ADMIN
            rec = "✅ NIVEL ÓPTIMO"
            if vencido: rec = "❌ RETIRAR: PRODUCTO VENCIDO"
            elif stock <= minimo: rec = "⚠️ REPOSICIÓN URGENTE"
            elif stock > (minimo * 3): rec = "📦 SOBRE-STOCK: Evaluar promoción"
            elif margen < 15: rec = "📉 REVISAR PRECIO/COSTO"

            return (f"AUDITORÍA: {match[0]} ({es_pareto}). "
                    f"Margen: {margen:.1f}%. Stock: {stock}. "
                    f"Ubicación: {fila['Ubicación']}. Predicción: {rec}")
    
    return "Elena: No logré localizar ese producto en el inventario actual."

@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Base de datos sincronizada. Modo Senior activo."})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 55.4), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error: Sin Datos", 400
    
    df = inventario["df"]
    hoy = datetime.now()
    faltantes = df[df['Stock Actual'] <= df['Stock Mínimo']]
    vencidos = df[pd.to_datetime(df['Vencimiento']) < hoy]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "REPORTE DE REPOSICION - ELENA AI", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(200, 10, f"Generado el: {hoy.strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)

    # Tabla Faltantes
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "PRODUCTOS CON STOCK CRITICO", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, f in faltantes.iterrows():
        pdf.cell(190, 7, f"- {f['Producto']}: {f['Stock Actual']} unidades (Min: {f['Stock Mínimo']})", ln=True)
    
    pdf.ln(5)
    # Tabla Vencidos
    pdf.set_fill_color(255, 230, 230)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "ALERTAS DE VENCIMIENTO", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, v in vencidos.iterrows():
        pdf.cell(190, 7, f"- {v['Producto']}: Vencio el {v['Vencimiento']}", ln=True)

    output = io.BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_bytes)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f"Cierre_{hoy.strftime('%d%m%Y')}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))