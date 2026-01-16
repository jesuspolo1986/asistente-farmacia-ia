import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime

app = Flask(__name__)

# Memoria global para que todas las PCs vean lo mismo
inventario = {"df": None, "tasa": 325.40}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia']
}

@app.route('/')
def home():
    # Detecta el rol desde la URL (?rol=admin)
    rol = request.args.get('rol', 'vendedor')
    return render_template('index.html', modo=rol, tasa=inventario["tasa"])

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
        return jsonify({"success": True, "mensaje": "Inventario Sincronizado para todas las terminales."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: El administrador aún no ha cargado el inventario hoy."})
    
    df = inventario["df"]
    pregunta = data.get("pregunta", "").lower().replace("precio", "").strip()
    modo_admin = data.get("modo_admin", False)
    tasa = float(data.get("tasa", 325.40))

    match = process.extractOne(pregunta, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        if modo_admin:
            m = ((f['Precio Venta'] - f['Costo']) / f['Precio Venta']) * 100 if f['Precio Venta'] > 0 else 0
            res = f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${f['Precio Venta']:.2f} | Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}"
        else:
            res = f"El {match[0]} cuesta {f['Precio Venta']*tasa:,.2f} BS (${f['Precio Venta']:,.2f} USD). Stock: {int(f['Stock Actual'])}."
        return jsonify({"respuesta": res})

    return jsonify({"respuesta": "Producto no encontrado."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))