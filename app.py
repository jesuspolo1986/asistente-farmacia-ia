import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils
import re # Para limpiar la pregunta

app = Flask(__name__)
inventario = {"df": None, "tasa": 55.40}

def limpiar_pregunta(texto):
    """Elimina frases comunes para dejar solo el nombre del producto"""
    texto = texto.lower()
    frases_a_quitar = [
        "cuanto cuesta", "dame el precio de", "precio de", "precio del",
        "cuanto vale", "en cuanto esta", "tienes", "hablar de", "buscame"
    ]
    for frase in frases_a_quitar:
        texto = texto.replace(frase, "")
    return texto.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None:
        return "Elena: No he detectado el archivo de inventario. Por favor, cárguelo."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 

    # Limpiamos la pregunta para que Elena entienda: "¿Cuánto cuesta la Loratadina?" -> "Loratadina"
    producto_buscado = limpiar_pregunta(pregunta_original)
    
    productos = inventario["df"]['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    nota = " [Nota: Suscripción en Gracia]."

    if match and match[1] > 60: # Bajamos un poco el umbral para ser más flexibles
        fila = inventario["df"][inventario["df"]['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        if not modo_admin:
            # MODO PÚBLICO: Solo precio y salud
            return (f"El activo {match[0]} tiene un valor de {precio_usd} USD, "
                    f"equivalente a {precio_bs:,.2f} Bolívares. ¿Desea que se lo reserve?")
        else:
            # MODO ADMINISTRATIVO: Reporte Técnico Exhaustivo
            stock = int(fila['Stock Actual'])
            minimo = int(fila['Stock Mínimo'])
            ubi = fila['Ubicación']
            vence = fila['Vencimiento']
            alerta = "🚨 RECOMPRA INMEDIATA" if stock <= minimo else "✅ NIVEL ÓPTIMO"
            
            # Aquí forzamos que Elena responda como jefa de inventario
            return (f"REPORTE DE AUDITORÍA: {match[0]}. "
                    f"Costo en sistema: {precio_usd} USD ({precio_bs:,.2f} BS). "
                    f"Existencia real: {stock} unidades. Mínimo requerido: {minimo}. "
                    f"Estado: {alerta}. Ubicación física: {ubi}. Vencimiento: {vence}.{nota}")
    
    return f"No logré identificar el producto '{producto_buscado}' en el inventario actual.{nota}"

# ... (Resto de las rutas /index, /upload, /preguntar igual que el anterior) ...

@app.route('/')
def index():
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": f"Base de datos lista: {len(df)} productos."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    pregunta = data.get("pregunta", "")
    tasa_f = data.get("tasa", 55.40)
    es_admin = data.get("modo_admin", False)
    respuesta = buscar_analisis_senior(pregunta, tasa_f, es_admin)
    return jsonify({"respuesta_asistente": respuesta})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)