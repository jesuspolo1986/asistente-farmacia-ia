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
        return jsonify({"respuesta_asistente": "Por favor, carga el archivo de inventario primero."})
    
    try:
        # 1. Limpieza del término buscado
        termino = "".join(e for e in nombre if e.isalnum() or e.isspace()).lower().strip()
        
        # 2. Búsqueda inteligente
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            fila = resultado.iloc[0].to_dict()
            # LIMPIEZA DE "GUION BAJO": Convertimos las claves para que Elena no las deletree
            # Ejemplo: 'precio_venta' se convierte en 'precio venta'
            datos_limpios = {k.replace('_', ' '): v for k, v in fila.items()}
            contexto = f"Producto: {datos_limpios}"
        else:
            contexto = "No encontrado."

        # 3. Llamada a la IA (Ajustada para evitar Error 400)
        # Usamos un formato más simple y directo
        prompt_sistema = "Eres Elena. Responde de forma natural y breve. NO menciones guiones bajos. Di el precio y existencia."
        prompt_usuario = f"Basado en estos datos: {contexto}. Responde sobre: {nombre}"

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7 # Añadimos temperatura para que suene más humana
        )
        
        respuesta = completion.choices[0].message.content
        return jsonify({"respuesta_asistente": respuesta})

    except Exception as e:
        print(f"Error detallado: {str(e)}")
        # Si el error es 400, suele ser por caracteres especiales en el Excel
        return jsonify({"respuesta_asistente": "Lo siento, tuve un problema al leer los datos. Revisa el formato del Excel."})
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)