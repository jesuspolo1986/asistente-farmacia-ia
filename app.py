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

# --- CONFIGURACIÓN DE IA (Inyección de Reglas Estrictas) ---
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
    if not file: return jsonify({"error": "No hay archivo"}), 400
    
    try:
        stream = io.BytesIO(file.read())
        df_inv = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)

        # SENIOR: Limpieza y Normalización de Base de Datos
        df_inv.columns = [str(c).replace("_", " ").strip().title() for c in df_inv.columns]
        df_inv = df_inv.fillna("No disponible")
        
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": f"Error al procesar Excel: {str(e)}"}), 500

ado = df_inv[mask]
        
        if not resultado.empty:
            # Seleccionamos la primera coincidencia y la convertimos en lenguaje humano
            fila = resultado.iloc[0].to_dict()
            contexto_datos = " | ".join([f"{k}: {v}" for k, v in fila.items()])
            encont@app.route('/preguntar/<nombre>', methods=['GET'])
@app.route('/preguntar/<nombre_completo>', methods=['GET'])
def preguntar_por_voz(nombre_completo):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Inventario no cargado."})
    
    try:
        # PASO 1: Usar la IA para extraer el producto (Nivel Senior)
        # Esto convierte "Cual es el precio de la loratadina" en solo "loratadina"
        extraer = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": "Tu tarea es extraer solo el nombre del medicamento de la frase. Responde SOLO con el nombre del producto, nada más."},
                {"role": "user", "content": nombre_completo}
            ]
        )
        producto_clave = extraer.choices[0].message.content.strip().lower()
        print(f"IA extrajo: {producto_clave}") # Para ver el proceso en Koyeb

        # PASO 2: Búsqueda flexible en el DataFrame
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(producto_clave)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            fila = resultado.iloc[0].to_dict()
            contexto = ", ".join([f"{k} es {v}" for k, v in fila.items()])
        else:
            contexto = "No encontrado."

        # PASO 3: Respuesta final de Elena
        prompt_final = (
            "Eres Elena. Usa los datos para responder de forma amable. "
            "Si el producto existe, da el precio y stock. Si no, di que no lo encontraste."
        )
        
        final = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": prompt_final},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta: {nombre_completo}"}
            ]
        )
        
        return jsonify({"respuesta_asistente": final.choices[0].message.content})

    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error: {str(e)}"})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)