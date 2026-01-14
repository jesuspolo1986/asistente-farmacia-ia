import os
import io
import pandas as pd
from flask import Flask, jsonify, render_template, request
from groq import Groq

app = Flask(__name__)
api_key_groq = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key_groq)

df_inv = None

@app.route('/')
def home():
    return render_template('index.html')

import io  # Asegúrate de tener esta importación arriba

@app.route('/upload', methods=['POST'])
def upload_file():
    global df_inv
    try:
        # 1. Verificación de seguridad básica
        if 'file' not in request.files:
            return jsonify({"error": "No se encontró el archivo en la petición"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío"}), 400

        # 2. LECTURA EN MEMORIA (Como en AI Pro Analyst)
        # Esto evita el error 500 porque no necesita escribir en el disco de Render
        data = file.read()
        stream = io.BytesIO(data)
        
        if file.filename.endswith('.csv'):
            # skipinitialspace ayuda con los CSV mal formados
            df_inv = pd.read_csv(stream, skipinitialspace=True)
        else:
            # engine='openpyxl' es vital para archivos .xlsx
            df_inv = pd.read_excel(stream, engine='openpyxl')

        # 3. LIMPIEZA INMEDIATA
        # Quitamos espacios y normalizamos columnas
        df_inv.columns = [str(c).strip() for c in df_inv.columns]
        # Convertimos todo a string para que las búsquedas no den error
        df_inv = df_inv.astype(str)

        print(f"Archivo cargado con éxito. Columnas: {list(df_inv.columns)}")
        
        return jsonify({
            "status": "Exitoso", 
            "filas": len(df_inv),
            "columnas": list(df_inv.columns)
        })

    except Exception as e:
        # Este print saldrá en tus logs de Render para decirte el error exacto
        print(f"ERROR CRÍTICO EN UPLOAD: {str(e)}")
        return jsonify({"error": f"Fallo interno: {str(e)}"}), 500
@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Sube el archivo primero."})
    
    try:
        # LIMPIEZA AGRESIVA: Quitamos puntos, comas y espacios (ej: "Ventas." -> "ventas")
        termino = "".join(filter(str.isalnum, nombre)).lower().strip()
        
        # Búsqueda en todo el DataFrame (Universal)
        # Convertimos todo a minúsculas para comparar
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            # Si hay resultados, tomamos los datos de la primera fila
            datos = resultado.iloc[0].to_dict()
            contexto = f"Datos encontrados: {datos}"
        else:
            # Si no hay resultados (como pasó con 'Ventas'), Elena debe ser honesta
            contexto = f"No encontré ningún producto o dato que coincida con '{nombre}'."

        # Prompt para Elena
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde por voz de forma breve. Si no encuentras el producto, dile al usuario qué productos sí tienes disponibles brevemente."},
                {"role": "user", "content": f"Contexto: {contexto}. Pregunta: {nombre}. Inventario actual: {df_inv.head(5).to_dict()}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"respuesta_asistente": "Tuve un problema al leer el archivo."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000)) # Ajustado al port 10000 de tus logs
    app.run(host='0.0.0.0', port=port)