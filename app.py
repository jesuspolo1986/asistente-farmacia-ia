import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF # Asegúrate de tener 'fpdf' en requirements.txt

app = Flask(__name__)

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

    # Sincronizar Tasa (SOLO SI ES ADMIN)
    if modo_admin and data.get("nueva_tasa"):
        inventario["tasa"] = float(data.get("nueva_tasa"))
        return jsonify({"respuesta": "TASA_OK", "tasa_sync": inventario["tasa"]})

    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: Inventario no cargado."})
    
    df = inventario["df"]
    match = process.extractOne(pregunta.replace("precio", "").strip(), df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa = inventario["tasa"]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * tasa
        
        if modo_admin:
            # MODO ADMIN: Dice TODO (incluyendo stock y ganancia)
            m = ((p_usd - f['Costo']) / p_usd) * 100 if p_usd > 0 else 0
            res = f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${p_usd:.2f} | Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}"
        else:
            # MODO VENDEDOR: Solo BS y USD. SIN STOCK.
            res = f"El {match[0]} cuesta {p_bs:,.2f} Bolívares, que equivalen a {p_usd:,.2f} Dólares."
        
        return jsonify({"respuesta": res, "tasa_sync": tasa})

    return jsonify({"respuesta": "No encontrado.", "tasa_sync": inventario["tasa"]})

@app.route('/descargar-reporte')
def descargar_reporte():
    try:
        if inventario["df"] is None: return "No hay datos", 400
        df = inventario["df"]
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "REPORTE DE FARMACIA", ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(200, 10, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(10)

        # Cálculos
        t_costo = (df['Costo'] * df['Stock Actual']).sum()
        t_venta = (df['Precio Venta'] * df['Stock Actual']).sum()

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Valor Total (Costo): ${t_costo:,.2f}", ln=True)
        pdf.cell(0, 10, f"Valor Total (Venta): ${t_venta:,.2f}", ln=True)
        
        output = io.BytesIO()
        pdf.output(output)
        output.seek(0)
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name="Reporte_Farmacia.pdf")
    except Exception as e:
        return str(e), 500

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
        return jsonify({"success": True, "mensaje": "Inventario sincronizado."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))