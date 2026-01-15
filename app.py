import os
import io
import pandas as pd
import requests
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils
from datetime import datetime

app = Flask(__name__)

# Memoria del sistema
inventario = {
    "df": None, 
    "tasa": 55.40, 
    "ultima_actualizacion": "Pendiente de sincronizar"
}

def obtener_tasa_venezuela():
    """Consulta la API de monitoreo y actualiza la memoria del sistema"""
    try:
        # API de monitoreo para Venezuela
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=enparalelovzla"
        response = requests.get(url, timeout=7)
        data = response.json()
        
        # Extraer precio de EnParaleloVzla
        nueva_tasa = float(data['monitors']['enparalelovzla']['price'])
        inventario["tasa"] = nueva_tasa
        inventario["ultima_actualizacion"] = datetime.now().strftime("%I:%M %p")
        return nueva_tasa
    except Exception as e:
        print(f"Error de conexión a tasa: {e}")
        return inventario["tasa"]

def buscar_analisis_senior(nombre_usuario):
    if inventario["df"] is None:
        return "Elena: No he detectado el archivo de inventario. Por favor, cárguelo para proceder."
    
    # Actualizamos la tasa justo antes de responder para máxima precisión
    tasa = obtener_tasa_venezuela()
    
    productos = inventario["df"]['Producto'].astype(str).tolist()
    match = process.extractOne(nombre_usuario, productos, processor=utils.default_process)
    
    # Mensaje de Día de Gracia (15 de enero)
    nota_pago = " [Estatus: Día de Gracia Activo]."

    if match and match[1] > 70:
        fila = inventario["df"][inventario["df"]['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        # Lógica de venta sugestiva (Upselling)
        sugerencia = ""
        tag = str(match[0]).lower()
        if "loratadina" in tag:
            sugerencia = "Como observación senior, recuerde que la hidratación es clave en alergias. "
        elif "amoxicilina" in tag:
            sugerencia = "Dada la naturaleza del antibiótico, sugiero verificar si requiere probióticos. "

        return (f"Análisis para {match[0]}: {precio_usd} USD. "
                f"Al cambio actual de {tasa} BS, el total es {precio_bs:,.2f} Bolívares. "
                f"{sugerencia}{nota_pago}")
    
    return f"No localizo '{nombre_usuario}' en la auditoría de stock actual.{nota_pago}"

@app.route('/')
def index():
    # Al cargar la página, Elena busca la tasa de inmediato
    tasa_hoy = obtener_tasa_venezuela()
    return render_template('index.html', tasa=tasa_hoy, fecha=inventario["ultima_actualizacion"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "Archivo no recibido"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": f"Sincronización exitosa: {len(df)} activos registrados."})
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