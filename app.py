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
    global df_inv, mapa_columnas
    try:
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            df_inv = pd.read_excel(file, engine='openpyxl')
        else:
            df_inv = pd.read_csv(file)
        
        # Limpieza básica
        df_inv = df_inv.fillna("No disponible")
        mapa_columnas = mapeo_universal(df_inv)
        
        return jsonify({
            "status": "Exitoso", 
            "filas": len(df_inv),
            "mapeo": mapa_columnas
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv, mapa_columnas
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Por favor, primero sube el archivo de inventario."})
    
    try:
        # Búsqueda universal: filtramos en la columna que detectamos como 'nombre' [cite: 2026-01-14]
        col_prod = mapa_columnas['nombre']
        resultado = df_inv[df_inv[col_prod].astype(str).str.contains(nombre, case=False, na=False)]
        
        if not resultado.empty:
            # Creamos un resumen limpio para la IA
            resumen = resultado.head(3).to_dict(orient='records')
            contexto = f"Encontré esto: {resumen}. "
        else:
            contexto = "No se encontró el producto exacto."

        # Elena responde por voz basándose en el mapeo [cite: 2026-01-14]
        prompt_sistema = (
            "Eres Elena. Responde de forma muy breve y humana para ser escuchada por voz. "
            f"Usa estos datos detectados: Columna de nombre es '{mapa_columnas['nombre']}', "
            f"precio es '{mapa_columnas['precio']}' y stock es '{mapa_columnas['stock']}'."
        )

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Datos: {contexto}. Pregunta: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        return jsonify({"respuesta_asistente": "Lo siento, tuve un problema al procesar la información del archivo."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)