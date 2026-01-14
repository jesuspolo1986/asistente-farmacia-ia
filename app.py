import os
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, render_template, session
from mistralai import Mistral
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_senior_2026")

# --- CONFIGURACIÓN DE IA (Inyección de Reglas Estrictas) ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

df_inv = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_inv
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    
    try:
        stream = io.BytesIO(file.read())
        df_inv = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)

        # SENIOR: Limpieza y Normalización de Base de Datos
        df_inv.columns = [str(c).replace("_", " ").strip().title() for c in df_inv.columns]
        df_inv = df_inv.fillna("No disponible")
        
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": f"Error al procesar Excel: {str(e)}"}), 500

@app.route('/preguntar/<nombre>', methods=['GET'])
def preguntar_por_voz(nombre):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "El sistema está listo, pero falta el inventario. Súbelo para empezar."})
    
    try:
        # SENIOR: Búsqueda Semántica Mejorada
        termino = "".join(e for e in nombre if e.isalnum() or e.isspace()).lower().strip()
        mask = df_inv.apply(lambda row: row.astype(str).str.lower().str.contains(termino)).any(axis=1)
        resultado = df_inv[mask]
        
        if not resultado.empty:
            # Seleccionamos la primera coincidencia y la convertimos en lenguaje humano
            fila = resultado.iloc[0].to_dict()
            contexto_datos = " | ".join([f"{k}: {v}" for k, v in fila.items()])
            encontrado = True
        else:
            contexto_datos = "PRODUCTO NO ENCONTRADO EN EXCEL."
            encontrado = False

        # SENIOR: System Prompt Blindado (Evita consejos médicos genéricos)
        prompt_sistema = (
            "Eres Elena, la Inteligencia Operativa de esta Farmacia. "
            "REGLAS CRÍTICAS:\n"
            "1. Tienes PROHIBIDO dar consejos médicos o sugerir ir a otras farmacias.\n"
            "2. Tu única fuente de información es el CONTEXTO DE DATOS proporcionado.\n"
            "3. Si el producto existe, responde: 'El [Nombre] tiene un precio de [Precio] y nos quedan [Stock]'.\n"
            "4. Si NO existe, responde: 'Lo siento, no tengo ese producto registrado en mi inventario actual'.\n"
            "5. Usa un tono profesional, amable y muy directo para voz."
        )

        response = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"CONTEXTO DE DATOS: {contexto_datos}\nPREGUNTA USUARIO: {nombre}"}
            ],
            temperature=0.1 # SENIOR: Temperatura baja = Menos inventiva, más precisión
        )
        
        return jsonify({"respuesta_asistente": response.choices[0].message.content})

    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error en procesamiento: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)