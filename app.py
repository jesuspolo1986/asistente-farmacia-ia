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
        return jsonify({"respuesta_asistente": "Todavía no tengo el inventario. Por favor, súbelo."})
    
    try:
        # 1. Aseguramos que el nombre buscado sea texto limpio
        termino = str(nombre).strip().lower()
        
        # 2. Buscamos de la forma más simple posible en todas las columnas
        # Creamos una copia temporal para no dañar el original
        df_temp = df_inv.astype(str)
        
        # Buscamos coincidencias
        resultado = df_temp[df_temp.apply(lambda x: x.str.lower().str.contains(termino)).any(axis=1)]
        
        if not resultado.empty:
            # Tomamos la primera coincidencia y la convertimos a un texto plano simple
            fila = resultado.iloc[0]
            contexto = f"Producto: {fila.get('nombre', 'N/A')}, Precio: {fila.get('precio', 'N/A')}, Stock: {fila.get('stock', 'N/A')}"
        else:
            contexto = f"No encontré el producto {nombre}."

        # 3. Llamada a Groq
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde por voz de forma muy breve con el precio y stock del producto encontrado."},
                {"role": "user", "content": f"Dato real: {contexto}. Pregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        print(f"ERROR CRÍTICO: {e}")
        return jsonify({"respuesta_asistente": "Lo siento, hubo un error de lectura. Intenta decir solo el nombre del medicamento."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)