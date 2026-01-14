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
    
    try:
        # Buscamos cuál es la columna que contiene los nombres de productos
        # Buscamos la primera columna que tenga texto (usualmente la primera o segunda)
        columna_producto = df_inv.columns[0] 
        
        # Filtramos con el nombre de columna detectado dinámicamente [cite: 2026-01-14]
        resultado = df_inv[df_inv[columna_producto].astype(str).str.contains(nombre, case=False, na=False)]
        
        if not resultado.empty:
            contexto = resultado.to_string(index=False)
        else:
            contexto = f"El producto '{nombre}' no aparece en el archivo."

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde de forma muy breve con precio y stock basados en los datos proporcionados."},
                {"role": "user", "content": f"Datos: {contexto}\nPregunta del cliente: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error al leer el archivo: {str(e)}"})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)