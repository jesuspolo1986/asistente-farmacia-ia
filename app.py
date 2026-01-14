import os
import io
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
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
        # Lectura en memoria (técnica de AI Pro Analyst)
        stream = io.BytesIO(file.read())
        
        if file.filename.endswith('.csv'):
            df_inv = pd.read_csv(stream)
        else:
            # Requiere openpyxl en requirements.txt
            df_inv = pd.read_excel(stream, engine='openpyxl')

        # Limpieza y normalización inmediata [cite: 2026-01-14]
        df_inv.columns = df_inv.columns.str.strip() # Mantenemos nombres originales para Elena
        df_inv = df_inv.fillna("No disponible")
        
        return jsonify({
            "status": "Exitoso", 
            "filas": len(df_inv),
            "columnas": list(df_inv.columns)
        })
    except Exception as e:
        print(f"Error en carga: {e}")
        return jsonify({"error": "Error al procesar el archivo"}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Por favor, primero sube el inventario."})
    
    try:
        # Búsqueda universal (Busca en todas las columnas como el Analista Pro)
        termino = nombre.lower().strip()
        # Convertimos temporalmente a string para la búsqueda
        mascara = df_inv.astype(str).apply(lambda row: row.str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mascara]
        
        if not resultado.empty:
            # Tomamos la primera coincidencia y la enviamos como contexto
            datos_producto = resultado.iloc[0].to_dict()
            contexto = f"Resultado encontrado: {datos_producto}"
        else:
            contexto = f"No se encontró el producto '{nombre}'."

        # Prompt optimizado para voz [cite: 2026-01-14]
        prompt_sistema = (
            "Eres Elena, asistente virtual de la farmacia. "
            "Tu respuesta será escuchada por voz, así que sé muy breve y clara. "
            "Dime el nombre del producto, su precio y el stock actual. "
            f"Estructura del inventario: {list(df_inv.columns)}"
        )

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta del cliente: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        print(f"Error en consulta: {e}")
        return jsonify({"respuesta_asistente": "Perdón, tuve un problema al buscar en el inventario."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)