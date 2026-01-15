import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils
from datetime import datetime

app = Flask(__name__)
inventario = {"df": None, "tasa": 55.40}

def limpiar_pregunta(texto):
    texto = texto.lower()
    # Añadimos más frases para que el usuario pueda hablar con total libertad
    frases_a_quitar = [
        "cuanto cuesta", "dame el precio de", "precio de", "precio del",
        "cuanto vale", "en cuanto esta", "tienes", "buscame", "dame el costo de"
    ]
    for frase in frases_a_quitar:
        texto = texto.replace(frase, "")
    return texto.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None:
        return "Elena: El inventario no ha sido cargado."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    producto_buscado = limpiar_pregunta(pregunta_original)
    
    productos = inventario["df"]['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = inventario["df"][inventario["df"]['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        # Lógica de Vencimiento
        venc_str = str(fila['Vencimiento'])
        try:
            fecha_venc = datetime.strptime(venc_str, '%Y-%m-%d')
            hoy = datetime.now()
            esta_vencido = fecha_venc < hoy
        except:
            esta_vencido = False

        if not modo_admin:
            if esta_vencido:
                return f"El activo {match[0]} no está disponible para la venta en este momento por protocolos de seguridad."
            return (f"El activo {match[0]} tiene un valor de {precio_usd} USD, "
                    f"equivalente a {precio_bs:,.2f} Bolívares. ¿Desea que se lo reserve?")
        else:
            stock = int(fila['Stock Actual'])
            minimo = int(fila['Stock Mínimo'])
            alerta_stock = "🚨 RECOMPRA URGENTE" if stock <= minimo else "✅ NIVEL ÓPTIMO"
            alerta_venc = "⚠️ ¡PRODUCTO VENCIDO! RETIRAR DE ESTANTE" if esta_vencido else "✅ Vigente"
            
            return (f"REPORTE ADMIN: {match[0]}. "
                    f"Costo: {precio_bs:,.2f} BS ({precio_usd} USD). "
                    f"Stock: {stock} (Mín: {minimo}). {alerta_stock}. "
                    f"Estado Sanitario: {alerta_venc}. Ubicación: {fila['Ubicación']}.")
    
    return f"No logré identificar '{producto_buscado}' en el inventario actual."

# ... (Mismas rutas @app.route para upload y preguntar) ...
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
        return jsonify({"success": True, "mensaje": f"Sincronizado: {len(df)} productos."})
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