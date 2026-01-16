import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

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
    
    # 1. COMANDO: Activar Admin
    if pregunta == "activar modo gerencia":
        return jsonify({"respuesta": "MODO_ADMIN_ACTIVADO"})

    # 2. SINCRONIZACIÓN DE TASA (Manual desde el input)
    if modo_admin and data.get("nueva_tasa"):
        inventario["tasa"] = float(data.get("nueva_tasa"))
        return jsonify({"respuesta": "TASA_OK", "tasa_sync": inventario["tasa"]})

    # 3. Búsqueda de productos
    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: Sincronice el inventario primero."})
    
    df = inventario["df"]
    p_busqueda = pregunta.replace("precio", "").strip()
    match = process.extractOne(p_busqueda, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa_actual = inventario["tasa"]
        precio_usd = float(f['Precio Venta'])
        precio_bs = precio_usd * tasa_actual
        
        if modo_admin:
            m = ((precio_usd - f['Costo']) / precio_usd) * 100 if precio_usd > 0 else 0
            res = f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${precio_usd:.2f} | Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}"
        else:
            res = f"El {match[0]} cuesta {precio_bs:,.2f} Bolívares, que son {precio_usd:,.2f} Dólares. Stock: {int(f['Stock Actual'])}."
        
        return jsonify({"respuesta": res, "tasa_sync": tasa_actual})

    return jsonify({"respuesta": "Producto no encontrado.", "tasa_sync": inventario["tasa"]})

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
from fpdf import FPDF

@app.route('/descargar-reporte')
def descargar_reporte():
    if inventario["df"] is None: return "No hay datos", 400
    
    df = inventario["df"]
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "REPORTE DE GERENCIA - ELENA AI", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(200, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)

    # Cálculos rápidos
    total_costo = (df['Costo'] * df['Stock Actual']).sum()
    total_venta = (df['Precio Venta'] * df['Stock Actual']).sum()
    stock_bajo = df[df['Stock Actual'] < 5]

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, f"Valor Total Inventario (Costo): ${total_costo:,.2f}")
    pdf.ln(7)
    pdf.cell(100, 10, f"Valor Total Inventario (Venta): ${total_venta:,.2f}")
    pdf.ln(15)

    pdf.set_text_color(255, 0, 0)
    pdf.cell(100, 10, "PRODUCTOS CON STOCK CRITICO (<5 unidades):")
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(120, 8, "Producto", 1)
    pdf.cell(30, 8, "Stock", 1)
    pdf.cell(40, 8, "Ubicacion", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 9)
    for _, fila in stock_bajo.iterrows():
        pdf.cell(120, 8, str(fila['Producto'])[:60], 1)
        pdf.cell(30, 8, str(int(fila['Stock Actual'])), 1)
        pdf.cell(40, 8, str(fila.get('Ubicación', 'N/A')), 1)
        pdf.ln()

    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, mimetype='application/pdf', as_attachment=True, download_name="Reporte_Elena_Farmacia.pdf")
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))