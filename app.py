import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, session
from rapidfuzz import process, utils

app = Flask(__name__)
app.secret_key = 'elena_farmacia_2026_key'

# Memoria global
inventario = {"df": None, "tasa": 54.50}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario', 'precio_usd']
}

@app.route('/')
def home():
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    
    if "activar modo gerencia" in pregunta:
        return jsonify({"respuesta": "Modo gerencia activado. Puedes subir el archivo ahora.", "status": "MODO_ADMIN"})

    if inventario["df"] is None:
        return jsonify({"respuesta": "Hola, soy Elena. Por favor, carga el inventario en el panel para poder ayudarte con los precios."})
    
    df = inventario["df"]
    # Búsqueda difusa para encontrar el producto
    match = process.extractOne(pregunta.replace("precio", "").strip(), df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * inventario["tasa"]
        res = f"El {match[0]} tiene un costo de {p_bs:,.2f} bolívares, que son {p_usd:,.2f} dólares."
        return jsonify({"respuesta": res})

    return jsonify({"respuesta": "Lo siento, no logré encontrar ese producto. ¿Podrías decirme el nombre de nuevo?"})

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('archivo')
    if not file: return jsonify({"success": False, "mensaje": "No se recibió archivo"})
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(stream)
        else:
            df = pd.read_csv(stream)
        
        # Normalizar columnas para que Elena entienda el Excel
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        
        if 'Producto' not in df.columns or 'Precio Venta' not in df.columns:
            return jsonify({"success": False, "mensaje": "El Excel no tiene las columnas necesarias (Producto/Precio)."})

        inventario["df"] = df
        return jsonify({"success": True, "mensaje": f"Inventario cargado: {len(df)} productos listos."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)