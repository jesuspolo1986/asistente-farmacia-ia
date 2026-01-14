import os
import pandas as pd
from flask import Flask, jsonify, render_template, request
from groq import Groq

app = Flask(__name__)

# Configuración de Groq
api_key_groq = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key_groq)

# Variables globales de inventario y mapeo
df_inv = None
mapa_columnas = {"nombre": None, "precio": None, "stock": None}

def mapeo_universal(df):
    """Analiza el Excel y detecta qué columna es cada cosa de forma inteligente"""
    cols = [c.lower() for c in df.columns]
    mapping = {}
    
    # 1. Buscar columna de NOMBRE (la que tiene más texto largo)
    mapping['nombre'] = next((c for c in df.columns if any(x in c.lower() for x in ['prod', 'nom', 'desc', 'art', 'item'])), df.columns[0])
    
    # 2. Buscar columna de PRECIO (la que tiene 'pre', 'cost', 'val' o '$')
    mapping['precio'] = next((c for c in df.columns if any(x in c.lower() for x in ['pre', 'cost', 'val', '$'])), None)
    
    # 3. Buscar columna de STOCK (la que tiene 'cant', 'stock', 'exist', 'und'])
    mapping['stock'] = next((c for c in df.columns if any(x in c.lower() for x in ['cant', 'stoc', 'exist', 'und', 'qty'])), None)
    
    return mapping

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global df_inv
    try:
        file = request.files['file']
        if file.filename.endswith('.csv'):
            df_inv = pd.read_csv(file)
        else:
            df_inv = pd.read_excel(file, engine='openpyxl')
        
        # --- EL TRUCO MAESTRO ---
        # Convertimos TODO el dataframe a string y limpiamos espacios
        df_inv = df_inv.astype(str).apply(lambda x: x.str.strip())
        # Ponemos los nombres de las columnas en minúsculas para el sistema
        df_inv.columns = df_inv.columns.str.strip().str.lower()
        
        return jsonify({"status": "Exitoso", "filas": len(df_inv)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Primero sube el inventario."})
    
    try:
        # Buscamos en todas las columnas, ahora que todo es texto es imposible que falle
        mascara = df_inv.apply(lambda row: row.str.contains(nombre, case=False).any(), axis=1)
        resultado = df_inv[mascara]
        
        if not resultado.empty:
            # Convertimos a una lista simple de texto para Elena
            datos = resultado.head(2).to_dict(orient='records')
            contexto = f"Medicamentos encontrados: {datos}"
        else:
            contexto = f"No tengo información sobre {nombre}."

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde por voz: di el nombre, el precio y el stock de forma muy breve."},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    except Exception as e:
        # Log para que tú veas qué pasó en Render si algo falla
        print(f"DEBUG: {e}")
        return jsonify({"respuesta_asistente": "Perdón, tuve un error al procesar la fila."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)