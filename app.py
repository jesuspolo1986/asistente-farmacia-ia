import os
import pandas as pd
from flask import Flask, jsonify, render_template, request
from groq import Groq

app = Flask(__name__)

# Configuración de Groq
api_key_groq = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key_groq)

# Variable global para el inventario
df_inv = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global df_inv
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nombre vacío"}), 400

    # Cargamos el archivo directamente a memoria
    if file.filename.endswith('.xlsx'):
        df_inv = pd.read_excel(file)
    else:
        df_inv = pd.read_csv(file)
    
    return jsonify({"status": "Inventario cargado", "filas": len(df_inv)})

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Primero sube el inventario, por favor."})
    
    # Buscamos el producto por nombre [cite: 2026-01-14]
    # Filtramos filas que contengan el nombre buscado
    resultado = df_inv[df_inv['producto'].str.contains(nombre, case=False, na=False)]
    
    if not resultado.empty:
        contexto = resultado.to_string(index=False)
    else:
        contexto = "Producto no encontrado en la lista."

    # Enviamos a la IA para una respuesta humana
    completion = client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=[
            {"role": "system", "content": "Eres Elena. Da precio y stock de forma amable."},
            {"role": "user", "content": f"Datos: {contexto}\nPregunta: {nombre}"}
        ],
    )
    return jsonify({"respuesta_asistente": completion.choices[0].message.content})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)