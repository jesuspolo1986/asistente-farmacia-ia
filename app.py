import os
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg') # - Crucial para que no falle en Koyeb
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, render_template, session
from mistralai import Mistral # - Usando la librería oficial como en AI Pro

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_secret_2026")

# --- CONFIGURACIÓN DE IA (Estilo AI Pro) ---
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
        # Lectura en memoria para evitar errores de disco en Koyeb
        stream = io.BytesIO(file.read())
        if file.filename.endswith('.csv'):
            df_inv = pd.read_csv(stream)
        else:
            df_inv = pd.read_excel(stream)

        # --- LIMPIEZA DE DATOS (Lo que evita el Error 400) ---
        df_inv = df_inv.fillna("No disponible") #
        # Normalizamos columnas: quitamos guiones bajos para que Elena no los diga
        df_inv.columns = [str(c).replace("_", " ").strip().capitalize() for c in df_inv.columns]
        
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Sube el inventario primero."})
    
    try:
        # Búsqueda adaptada: buscamos el producto por nombre [cite: 2026-01-14]
        termino = "".join(e for e in nombre if e.isalnum() or e.isspace()).lower().strip()
        
        # Buscamos en todas las filas (Case insensitive)
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            fila = resultado.iloc[0].to_dict()
            # Convertimos datos en frase humana para evitar que diga "guion bajo"
            contexto = ", ".join([f"{k} es {v}" for k, v in fila.items()])
        else:
            contexto = f"No encontré información sobre {nombre}."

        # Llamada a Mistral usando la estructura de AI Pro
        response = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": "Eres Elena, asistente de farmacia. Responde de forma breve y natural. NO menciones términos técnicos ni guiones."},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta: {nombre}"}
            ]
        )
        return jsonify({"respuesta_asistente": response.choices[0].message.content})

    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error técnico: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)