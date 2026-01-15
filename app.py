import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

app = Flask(__name__)
df_inv = None

def buscar_en_inventario(texto):
    global df_inv
    if df_inv is None: return "Elena: Aún no he cargado el inventario."
    
    # Normalizamos las columnas para buscar
    productos = df_inv['Producto'].astype(str).tolist()
    resultado = process.extractOne(texto, productos, processor=utils.default_process)
    
    # Si la coincidencia es mayor al 70%
    if resultado and resultado[1] > 70:
        fila = df_inv[df_inv['Producto'] == resultado[0]].iloc[0]
        precio = fila['Precio Venta']
        return f"Elena: El producto '{resultado[0]}' tiene un precio de ${precio}."
    return f"Elena: No encontré '{texto}' en el inventario actual."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_inv
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    try:
        stream = io.BytesIO(file.read())
        df_inv = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        # Limpieza rápida de nombres de columnas
        df_inv.columns = [str(c).strip().title() for c in df_inv.columns]
        return jsonify({"success": True, "productos": len(df_inv)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "")
    # Recordatorio del día de gracia (15 de enero)
    aviso = "\n(Nota: Suscripción en día de gracia)."
    respuesta = buscar_en_inventario(pregunta) + aviso
    return jsonify({"respuesta_asistente": respuesta})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)