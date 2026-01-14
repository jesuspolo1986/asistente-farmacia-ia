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
        # Forzamos la lectura limpia
        df_inv = pd.read_csv(file, skipinitialspace=True)
        # Limpiamos los nombres de las columnas de cualquier espacio loco
        df_inv.columns = df_inv.columns.str.strip() 
        return jsonify({"status": "Exitoso", "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Todavía no tengo el inventario. Por favor, súbelo."})
    
    try:
        # 1. Limpiamos el nombre que llega por voz
        termino = str(nombre).strip().lower()
        
        # 2. BÚSQUEDA DIRECTA Y SEGURA
        # Buscamos en la columna 'Nombre' (convertida a minúsculas para comparar)
        # Usamos .values[0] para obtener los datos de forma rápida y sin errores de índice
        resultado = df_inv[df_inv['Nombre'].astype(str).str.lower().str.contains(termino, na=False)]
        
        if not resultado.empty:
            # Extraemos los datos de la primera fila encontrada de forma manual
            prod_nom = resultado.iloc[0]['Nombre']
            prod_pre = resultado.iloc[0]['Precio']
            prod_sto = resultado.iloc[0]['Stock']
            contexto = f"Producto: {prod_nom}, Precio: {prod_pre}, Stock: {prod_sto}"
        else:
            contexto = f"No encontré el producto {nombre} en el inventario."

        # 3. Respuesta de Elena
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde por voz de forma muy breve. Di solo el precio y las unidades disponibles."},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        # Este print aparecerá en tus logs de Render para que sepas qué pasó exactamente
        print(f"Error específico en la búsqueda: {e}")
        return jsonify({"respuesta_asistente": "Perdón, tuve un problema con el archivo. Intenta subirlo de nuevo."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)