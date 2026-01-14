import os
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, render_template, session
from mistralai import Mistral
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_senior_2026")

# --- CONFIGURACIÓN DE IA ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

df_inv = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_inv
    file = request.files.get('file')
    if not file: 
        return jsonify({"error": "No hay archivo"}), 400
    
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df_inv = pd.read_excel(stream)
        else:
            df_inv = pd.read_csv(stream)

        # SENIOR: Normalización de columnas para evitar "guiones bajos" en la voz
        df_inv.columns = [str(c).replace("_", " ").strip().title() for c in df_inv.columns]
        df_inv = df_inv.fillna("No disponible")
        
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": f"Error al procesar archivo: {str(e)}"}), 500

@app.route('/preguntar/<nombre_completo>', methods=['GET'])
def preguntar_por_voz(nombre_completo):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "El inventario no está cargado."})
    
    try:
        # PASO 1: Convertimos el inventario a un resumen de texto para la IA
        # Esto le permite a Elena "leer" toda la tabla de una vez
        resumen_inventario = df_inv.to_string(index=False)
        fecha_hoy = "2026-01-14" # Fecha actual del sistema

        # PASO 2: Prompt Maestro (Nivel AI Pro Analyst)
        prompt_sistema = f"Eres Elena, asistente experta de farmacia. Hoy es {fecha_hoy}. " \
                         "Tienes acceso a este inventario:\n" \
                         f"{resumen_inventario}\n" \
                         "REGLAS:\n" \
                         "1. Si preguntan por vencimientos, compara la fecha de hoy con la columna 'Vencimiento'.\n" \
                         "2. Si preguntan por stock bajo, compara 'Stock Actual' con 'Stock Mínimo'.\n" \
                         "3. Responde de forma amable y profesional."

        response = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": nombre_completo}
            ],
            temperature=0
        )
        
        respuesta = response.choices[0].message.content
        return jsonify({"respuesta_asistente": respuesta})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"respuesta_asistente": "Error al analizar los datos."})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)