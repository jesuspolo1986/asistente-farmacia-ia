import os
import io
import pandas as pd
from flask import Flask, jsonify, render_template, request
from groq import Groq

app = Flask(__name__)

# Configuración de Groq
api_key_groq = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key_groq)

# Variable global (La reforzaremos con una validación de seguridad)
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
            return jsonify({"error": "No hay archivo"}), 400
        
        # LEER COMO EN AI PRO: Usando BytesIO para evitar errores de disco
        stream = io.BytesIO(file.read())
        
        if file.filename.endswith('.csv'):
            df_inv = pd.read_csv(stream)
        else:
            df_inv = pd.read_excel(stream, engine='openpyxl')

        # LIMPIEZA NIVEL PRO:
        # 1. Quitamos espacios en blanco de los nombres de columnas
        df_inv.columns = [str(c).strip() for c in df_inv.columns]
        # 2. Convertimos todo el contenido a string para que la búsqueda no falle con números
        df_inv = df_inv.astype(str)
        
        print(f"Columnas cargadas: {list(df_inv.columns)}") # Ver esto en los logs de Render
        
        return jsonify({
            "status": "Exitoso", 
            "filas": len(df_inv),
            "columnas": list(df_inv.columns)
        })
    except Exception as e:
        return jsonify({"error": f"Error técnico: {str(e)}"}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    # Si la variable se borró por reinicio del servidor, avisamos
    if df_inv is None:
        return jsonify({"respuesta_asistente": "El servidor se reinició. Por favor, sube el archivo de nuevo."})
    
    try:
        termino = str(nombre).lower().strip()
        
        # BÚSQUEDA UNIVERSAL DE AI PRO:
        # Buscamos en todas las celdas sin importar la columna
        mascara = df_inv.apply(lambda row: row.str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mascara]
        
        if not resultado.empty:
            # Convertimos la primera fila a un formato que Elena entienda
            fila_datos = resultado.iloc[0].to_dict()
            contexto = f"Datos del producto: {fila_datos}"
        else:
            contexto = f"No encontré el producto {nombre}."

        prompt_sistema = (
            "Eres Elena. Responde por voz de forma muy breve. "
            "Usa los datos proporcionados para decir el precio y el stock. "
            "Si no hay datos claros, dilo con amabilidad."
        )

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Contexto: {contexto}. Pregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return jsonify({"respuesta_asistente": "Tuve un problema al leer la fila. Intenta decir solo el nombre."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)