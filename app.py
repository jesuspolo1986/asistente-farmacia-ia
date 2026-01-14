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
        return jsonify({"respuesta_asistente": "Todavía no tengo el inventario. Por favor, súbelo."})
    
    try:
        # Limpiamos los nombres de las columnas por si tienen espacios locos
        df_inv.columns = df_inv.columns.str.strip().str.lower()
        
        # Intentamos encontrar la columna de nombres (producto, nombre, articulo...)
        posibles_nombres = ['producto', 'nombre', 'articulo', 'descripcion']
        col_busqueda = next((c for c in posibles_nombres if c in df_inv.columns), df_inv.columns[0])

        # Buscamos el producto [cite: 2026-01-14]
        # Convertimos todo a texto para evitar errores con números
        mascara = df_inv[col_busqueda].astype(str).str.contains(nombre, case=False, na=False)
        resultado = df_inv[mascara]
        
        if not resultado.empty:
            # Tomamos solo las primeras 3 coincidencias para que Elena no hable demasiado
            contexto = resultado.head(3).to_string(index=False)
        else:
            contexto = "No encontré ese producto, pero puedo ayudarte con otro."

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Escuchaste una pregunta y debes responder solo con el precio y stock disponible de forma muy breve y clara para ser escuchada."},
                {"role": "user", "content": f"Inventario: {contexto}\nPregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        print(f"Error detallado: {e}") # Esto aparecerá en los logs de Render
        return jsonify({"respuesta_asistente": "Perdón, tuve un problema al leer los datos. ¿Podrías revisar el formato del Excel?"})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)