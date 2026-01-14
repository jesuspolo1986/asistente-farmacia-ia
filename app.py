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
        return jsonify({"respuesta_asistente": "El inventario no ha sido cargado aún."})
    
    try:
        # PASO 1: Extracción de Entidad (IA) - Limpia la frase del usuario
        extraer = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": "Extrae solo el nombre del medicamento. Responde SOLAMENTE el nombre."},
                {"role": "user", "content": nombre_completo}
            ],
            temperature=0
        )
        producto_clave = extraer.choices[0].message.content.strip().lower()
        print(f"Buscando producto: {producto_clave}")

        # PASO 2: Búsqueda en DataFrame
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(producto_clave)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            fila = resultado.iloc[0].to_dict()
            # Convertimos a formato legible para la IA
            contexto = " | ".join([f"{k}: {v}" for k, v in fila.items()])
        else:
            contexto = "No encontrado en el inventario."

        # PASO 3: Respuesta final de Elena (Voz natural)
        prompt_final = (
            "Eres Elena, asistente de farmacia. Tu respuesta será leída por voz. "
            "Usa los datos proporcionados para dar precio y stock. "
            "Si no encuentras el producto, sé amable y di que no está disponible."
        )
        
        final = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": prompt_final},
                {"role": "user", "content": f"DATOS: {contexto}. PREGUNTA: {nombre_completo}"}
            ],
            temperature=0.2
        )
        
        return jsonify({"respuesta_asistente": final.choices[0].message.content})

    except Exception as e:
        print(f"Error en el proceso: {e}")
        return jsonify({"respuesta_asistente": "Lo siento, tuve un problema técnico al procesar tu solicitud."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)