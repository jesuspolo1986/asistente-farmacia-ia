import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

app = Flask(__name__)

# Configuración Global
df_inv = None
TASA_CAMBIO = 55.40  # Ajusta esta tasa a tu moneda local

def buscar_analisis_senior(nombre_usuario):
    global df_inv
    if df_inv is None:
        return "Elena: El ecosistema de datos no ha sido sincronizado. Por favor, provea el inventario para iniciar el análisis estratégico."
    
    # Normalización de nombres en el Excel (Columna 'Producto')
    productos = df_inv['Producto'].astype(str).tolist()
    match = process.extractOne(nombre_usuario, productos, processor=utils.default_process)
    
    # Hoy es 15 de enero: Día de gracia
    nota_suscripcion = " [Nota: Su suscripción se encuentra en periodo de gracia de 24 horas]."

    if match and match[1] > 70:
        fila = df_inv[df_inv['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_local = precio_usd * TASA_CAMBIO
        
        respuesta = (
            f"He localizado el activo: {match[0]}. "
            f"Su valoración estratégica es de {precio_usd} dólares, "
            f"equivalente a {precio_local:,.2f} en moneda local. "
        )
        
        # Comentario financiero Senior
        if precio_usd > 20:
            respuesta += "Dada la magnitud de esta inversión, le sugiero verificar la rotación de stock. "
        else:
            respuesta += "Este valor se mantiene en niveles de alta competitividad de mercado. "
            
        return respuesta + nota_suscripcion
    
    return f"Tras un escaneo exhaustivo, no localizo '{nombre_usuario}'. ¿Desea que analice opciones de sustitución?" + nota_suscripcion

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_inv
    file = request.files.get('file')
    if not file: return jsonify({"error": "No se recibió archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df_inv = pd.read_excel(stream)
        else:
            df_inv = pd.read_csv(stream)
        
        # Limpieza Senior de columnas
        df_inv.columns = [str(c).strip().title() for c in df_inv.columns]
        return jsonify({"success": True, "mensaje": f"Sincronización exitosa: {len(df_inv)} activos financieros registrados."})
    except Exception as e:
        return jsonify({"error": f"Falla en la integridad de datos: {str(e)}"}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "")
    respuesta = buscar_analisis_senior(pregunta)
    return jsonify({"respuesta_asistente": respuesta})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)