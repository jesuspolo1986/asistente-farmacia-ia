import os
import io
import pandas as pd
import requests
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils
from datetime import datetime

app = Flask(__name__)

# Configuración Global de Consultoría
inventario = {"df": None, "tasa": 55.40, "ultima_actualizacion": None}

def obtener_tasa_venezuela():
    """Busca la tasa en tiempo real de EnParaleloVzla"""
    ahora = datetime.now()
    # Solo actualizamos si ha cambiado el día o si no tenemos tasa (Elena es eficiente)
    try:
        # Usamos una API pública para monitoreo de dólar en Venezuela
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=enparalelovzla"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Extraemos el monitor principal
        nueva_tasa = float(data['monitors']['enparalelovzla']['price'])
        inventario["tasa"] = nueva_tasa
        inventario["ultima_actualizacion"] = ahora.strftime("%d/%m/%Y %I:%M %p")
        return nueva_tasa
    except Exception as e:
        print(f"Error consultando tasa: {e}")
        return inventario["tasa"]

def buscar_analisis_senior(nombre_usuario):
    if inventario["df"] is None:
        return "Elena: El sistema de inventario no ha sido cargado. Por favor, suministre el archivo Excel."
    
    # Actualizar tasa automáticamente antes de cada consulta
    tasa = obtener_tasa_venezuela()
    
    productos = inventario["df"]['Producto'].astype(str).tolist()
    match = process.extractOne(nombre_usuario, productos, processor=utils.default_process)
    
    # Nota de suscripción (Hoy 15 de enero)
    nota = " [Suscripción: Día de Gracia Activo]."

    if match and match[1] > 70:
        fila = inventario["df"][inventario["df"]['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        # Lógica de Sugerencia (Cross-selling)
        sugerencia = ""
        tag = str(match[0]).lower()
        if "loratadina" in tag:
            sugerencia = "Como experta, le recuerdo que la hidratación es vital en procesos alérgicos. "
        elif "ibuprofeno" in tag:
            sugerencia = "Sugiero acompañar con un protector gástrico para su seguridad. "

        return (f"He auditado '{match[0]}'. Valor: {precio_usd} USD, equivalentes a {precio_bs:,.2f} Bolívares "
                f"según la tasa monitor de {tasa}. {sugerencia}{nota}")
    
    return f"No localizo el activo '{nombre_usuario}' en los registros actuales.{nota}"

@app.route('/')
def index():
    tasa = obtener_tasa_venezuela() # Carga inicial
    return render_template('index.html', tasa=tasa, fecha=inventario["ultima_actualizacion"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": f"Inventario sincronizado: {len(df)} productos."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "")
    respuesta = buscar_analisis_senior(pregunta)
    return jsonify({
        "respuesta_asistente": respuesta,
        "tasa_actual": inventario["tasa"],
        "ultima_act": inventario["ultima_actualizacion"]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)