import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

app = Flask(__name__)

# Memoria global única
inventario = {"df": None, "tasa": 325.40}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia']
}

@app.route('/')
def home():
    # Solo existe esta ruta, imposible que de 404
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    modo_admin = data.get("modo_admin", False)
    
    # CLAVE MAESTRA: Si el usuario escribe esto, Elena confirma el modo
    if pregunta == "activar modo gerencia":
        return jsonify({"respuesta": "MODO_ADMIN_ACTIVADO"})

    if inventario["df"] is None:
        return jsonify({"respuesta": "Elena: Inventario no cargado. Inicie sesión como admin para subir el archivo."})
    
    df = inventario["df"]
    p_busqueda = pregunta.replace("precio", "").strip()
    match = process.extractOne(p_busqueda, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        tasa = float(data.get("tasa", 325.40))
        if modo_admin:
            m = ((f['Precio Venta'] - f['Costo']) / f['Precio Venta']) * 100 if f['Precio Venta'] > 0 else 0
            res = f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${f['Precio Venta']:.2f} | Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}"
        else:
            res = f"El {match[0]} cuesta {f['Precio Venta']*tasa:,.2f} BS (${f['Precio Venta']:,.2f} USD). Stock: {int(f['Stock Actual'])}."
        return jsonify({"respuesta": res})

    return jsonify({"respuesta": "No encontré ese producto."})

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