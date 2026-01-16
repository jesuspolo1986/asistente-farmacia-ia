import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)

# Memoria global sincronizada
inventario = {"df": None, "tasa": 36.50}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia']
}

@app.route('/')
def home():
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    modo_admin = data.get("modo_admin", False)
    
    if pregunta == "activar modo gerencia":
        return jsonify({"respuesta": "MODO_ADMIN_ACTIVADO"})

    # Sincronización de tasa (Solo Admin)
    if modo_admin and data.get("nueva_tasa"):
        try:
            inventario["tasa"] = float(data.get("nueva_tasa"))
            return jsonify({"respuesta": "TASA_OK", "tasa_sync": inventario["tasa"]})
        except: pass

    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: Inventario vacío. Por favor cargue el Excel."})
    
    df = inventario["df"]
    p_busqueda = pregunta.replace("precio", "").strip()
    match = process.extractOne(p_busqueda, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa = inventario["tasa"]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * tasa
        
        if modo_admin:
            m = ((p_usd - f['Costo']) / p_usd) * 100 if p_usd > 0 else 0
            # CORREGIDO: Términos en Dólares para Admin
            res = f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${p_usd:.2f} | Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}"
        else:
            # CORREGIDO: Bolívares y Dólares para Vendedor, SIN STOCK
            res = f"El {match[0]} cuesta {p_bs:,.2f} Bolívares, que equivalen a {p_usd:,.2f} Dólares."
        
        return jsonify({"respuesta": res, "tasa_sync": tasa})

    return jsonify({"respuesta": "No encontré ese producto.", "tasa_sync": inventario["tasa"]})

@app.route('/descargar-reporte')
def descargar_reporte():
    try:
        if inventario["df"] is None: return "No hay datos", 400
        df = inventario["df"]
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "REPORTE DE FARMACIA - ELENA AI", ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(200, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(10)

        # Cálculos de inventario
        costo_total = (df['Costo'] * df['Stock Actual']).sum()
        venta_total = (df['Precio Venta'] * df['Stock Actual']).sum()

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Inversion Total (Costo): ${costo_total:,.2f}", ln=True)
        pdf.cell(0, 10, f"Valor de Venta Total: ${venta_total:,.2f}", ln=True)
        pdf.ln(5)
        
        # Tabla de Stock Bajo
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 10, "PRODUCTOS CON STOCK CRITICO:", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(140, 7, "Producto", 1)
        pdf.cell(40, 7, "Stock Actual", 1)
        pdf.ln()

        pdf.set_font("Arial", '', 8)
        bajo_stock = df[df['Stock Actual'] < 5].head(50) # Top 50 criticos
        for _, fila in bajo_stock.iterrows():
            pdf.cell(140, 6, str(fila['Producto'])[:80], 1)
            pdf.cell(40, 6, str(int(fila['Stock Actual'])), 1)
            pdf.ln()

        # SOLUCIÓN AL ERROR DE BYTESIO: Usar output(dest='S')
        pdf_content = pdf.output(dest='S').encode('latin-1')
        return send_file(
            io.BytesIO(pdf_content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Reporte_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        return f"Error generando PDF: {str(e)}", 500

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"success": False})
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inventario sincronizado con éxito."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))