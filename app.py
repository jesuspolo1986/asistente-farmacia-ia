import os
import io
import asyncio
import pandas as pd
import edge_tts  # <--- Nueva librería
from flask import Flask, request, jsonify, render_template, session, send_file
from rapidfuzz import process, utils

app = Flask(__name__)
app.secret_key = 'elena_farmacia_2026_key'

# Memoria global
inventario = {"df": None, "tasa": 54.50}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario', 'precio_usd']
}

# --- NUEVA RUTA PARA VOZ PREMIUM ---
@app.route('/leer_voz')
def leer_voz():
    texto = request.args.get('texto', '')
    if not texto:
        return "No hay texto", 400
    
    # Definimos la voz (Dalia es excelente para español de México/Latam)
    VOICE = "es-MX-DaliaNeural"
    
    # Función interna para manejar la corrutina de edge-tts
    async def generar_audio():
        communicate = edge_tts.Communicate(texto, VOICE)
        audio_stream = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])
        audio_stream.seek(0)
        return audio_stream

    # Ejecutamos el bucle asíncrono
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_memoria = loop.run_until_complete(generar_audio())
        return send_file(audio_memoria, mimetype="audio/mpeg")
    except Exception as e:
        return str(e), 500

@app.route('/')
def home():
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "").lower().strip()
    
    # Lógica de Modo Gerencia
    if "activar modo gerencia" in pregunta:
        return jsonify({
            "respuesta": "Modo gerencia activado. Puedes subir el archivo ahora.", 
            "status": "MODO_ADMIN",
            "modo_admin": True # Para que el frontend lo reconozca
        })

    if inventario["df"] is None:
        return jsonify({"respuesta": "Hola, soy Elena. Por favor, carga el inventario para poder ayudarte."})
    
    df = inventario["df"]
    # Búsqueda difusa
    match = process.extractOne(pregunta.replace("precio", "").strip(), df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        p_usd = float(f['Precio Venta'])
        p_bs = p_usd * inventario["tasa"]
        res = f"El {match[0]} tiene un costo de {p_bs:,.2f} bolívares, que son {p_usd:,.2f} dólares."
        return jsonify({
            "exito": True,
            "respuesta": res,
            "producto_nombre": match[0],
            "p_bs": f"{p_bs:,.2f}",
            "p_usd": f"{p_usd:,.2f}"
        })

    return jsonify({"respuesta": "Lo siento, no logré encontrar ese producto. ¿Podrías decirme el nombre de nuevo?"})

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('archivo')
    if not file: return jsonify({"success": False, "mensaje": "No se recibió archivo"})
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(stream)
        else:
            df = pd.read_csv(stream)
        
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        
        if 'Producto' not in df.columns or 'Precio Venta' not in df.columns:
            return jsonify({"success": False, "mensaje": "Faltan columnas Producto o Precio."})

        inventario["df"] = df
        return jsonify({"success": True, "productos": len(df)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)