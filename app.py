import os
import io
import pandas as pd
from flask import Flask, jsonify, render_template, request
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_koyeb_2026")

# Configuración Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

df_inv = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global df_inv
    try:
        file = request.files.get('file')
        if not file: return jsonify({"error": "No hay archivo"}), 400
        
        # Lectura en memoria (Igual que en AI Pro Analyst)
        stream = io.BytesIO(file.read())
        
        if file.filename.endswith('.csv'):
            df_inv = pd.read_csv(stream, skipinitialspace=True)
        else:
            df_inv = pd.read_excel(stream, engine='openpyxl')

        # Limpieza de nombres de columnas
        df_inv.columns = [str(c).strip().lower() for c in df_inv.columns]
        df_inv = df_inv.astype(str)
        
        return jsonify({"status": "Exitoso", "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "El inventario no ha sido cargado aún."})
    
    try:
        # 1. Limpieza extrema del nombre (quita puntos del dictado por voz)
        termino = "".join(e for e in nombre if e.isalnum() or e.isspace()).lower().strip()
        print(f"Buscando: {termino}") # Esto saldrá en tus logs de Koyeb

        # 2. Buscar en el DataFrame (Ajustado para buscar por nombre de producto)
        # Buscamos si el término está en alguna celda de la fila
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            datos_producto = resultado.iloc[0].to_dict()
            contexto = f"Producto encontrado: {datos_producto}"
        else:
            contexto = f"No encontré el producto {nombre} en el inventario."

        # 3. Llamada a Groq (Elena)
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena, una asistente de farmacia amable. Di el precio y el stock de forma muy breve para ser leída por voz."},
                {"role": "user", "content": f"Contexto: {contexto}. Pregunta del usuario: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})

    except Exception as e:
        # Imprime el error real en los logs de Koyeb para que podamos verlo
        print(f"ERROR REAL: {str(e)}") 
        return jsonify({"respuesta_asistente": f"Error técnico: {str(e)}"})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)