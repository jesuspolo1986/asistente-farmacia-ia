import os
import pandas as pd
from flask import Flask, jsonify, render_template
from groq import Groq

app = Flask(__name__)

# Configura tu llave de Groq aquí
KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key_groq)

# Carga el Excel (asegúrate de subirlo a la nube también)
df_inv = pd.read_excel('inventario.xlsx')

def obtener_respuesta_ia(consulta_usuario):
    try:
        # Filtrado rápido de inventario [cite: 2026-01-14]
        contexto = df_inv.head(10).to_string(index=False)

        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768", # Modelo potente y gratis
            messages=[
                {"role": "system", "content": "Eres Elena, asistente de Farmacia Pro. Responde en una frase corta con precio y stock."},
                {"role": "user", "content": f"Inventario: {contexto}\nPregunta: {consulta_usuario}"}
            ],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return "Servicio temporalmente fuera de línea."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    respuesta = obtener_respuesta_ia(nombre)
    return jsonify({"status": "Exitoso", "respuesta_asistente": respuesta})

if __name__ == '__main__':
    # Puerto dinámico para la nube
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)