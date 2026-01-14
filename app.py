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
        # Cargamos el archivo ignorando errores de formato
        if file.filename.endswith('.xlsx'):
            df_inv = pd.read_excel(file, engine='openpyxl')
        else:
            df_inv = pd.read_csv(file)
        
        # --- LIMPIEZA PROFUNDA ---
        # 1. Eliminamos filas que estén totalmente vacías
        df_inv = df_inv.dropna(how='all')
        
        # 2. Si las columnas tienen nombres como "Unnamed", 
        # intentamos usar la primera fila real como encabezado
        if "Unnamed" in str(df_inv.columns):
            df_inv.columns = df_inv.iloc[0]
            df_inv = df_inv[1:]
            
        # 3. Normalizamos todo a texto para evitar errores de búsqueda
        df_inv = df_inv.fillna("Desconocido")
        
        # 4. Mapeo inteligente
        mapa_columnas = mapeo_universal(df_inv)
        
        return jsonify({"status": "Exitoso", "filas": len(df_inv)})
    except Exception as e:
        print(f"Error fatal en carga: {e}")
        return jsonify({"error": "Formato de archivo no compatible"}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Todavía no tengo el inventario. Por favor, súbelo."})
    
    try:
        # DEPURACIÓN: Forzamos que todo sea string y buscamos en TODO el dataframe
        # Esto hace que el buscador sea 100% universal
        mascara = df_inv.apply(lambda row: row.astype(str).str.contains(nombre, case=False).any(), axis=1)
        resultado = df_inv[mascara]
        
        if not resultado.empty:
            # Convertimos a diccionario para que la IA lo entienda fácil
            datos_encontrados = resultado.head(2).to_dict(orient='records')
            contexto = f"Encontré estos datos: {datos_encontrados}"
        else:
            contexto = f"No encontré nada relacionado con {nombre}"

        # Configuración de voz de Elena
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "Eres Elena. Responde por voz de forma muy breve. Di el nombre del producto, su precio y cuántos quedan. Sé muy clara."},
                {"role": "user", "content": f"Datos del Excel: {contexto}\nPregunta del cliente: {nombre}"}
            ],
        )
        return jsonify({"respuesta_asistente": completion.choices[0].message.content})
    
    except Exception as e:
        # Si algo falla, imprimimos el error real en la consola de Render para verlo
        print(f"Error real: {str(e)}")
        return jsonify({"respuesta_asistente": "Hubo un pequeño error técnico al leer la fila. Intenta con otro nombre."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)