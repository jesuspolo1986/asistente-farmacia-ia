import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

app = Flask(__name__)

# Memoria del sistema: Tasa inicial por defecto
inventario = {"df": None, "tasa": 55.40}

def buscar_analisis_senior(nombre_usuario, tasa_recibida):
    if inventario["df"] is None:
        return "Elena: El inventario no ha sido cargado. Por favor, suministre el archivo Excel."
    
    # Usamos la tasa que viene directamente del input del usuario en el celular
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 

    productos = inventario["df"]['Producto'].astype(str).tolist()
    match = process.extractOne(nombre_usuario, productos, processor=utils.default_process)
    
    # Nota de suscripción (Hoy 15 de enero - Día de Gracia)
    nota = " [Nota: Período de Gracia Activo]."

    if match and match[1] > 70:
        fila = inventario["df"][inventario["df"]['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        # Lógica de Sugerencia Senior
        sugerencia = ""
        tag = str(match[0]).lower()
        if "loratadina" in tag:
            sugerencia = "Recuerde que la hidratación es vital en procesos alérgicos. "
        elif "ibuprofeno" in tag:
            sugerencia = "Sugiero acompañar con un protector gástrico para su seguridad. "

        return (f"He auditado '{match[0]}'. Valor: {precio_usd} USD, equivalentes a {precio_bs:,.2f} Bolívares "
                f"calculados a tasa de {tasa}. {sugerencia}{nota}")
    
    return f"No localizo el activo '{nombre_usuario}' en los registros actuales.{nota}"

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
    tasa_frontend = data.get("tasa", 55.40) # Recibe la tasa del input manual
    respuesta = buscar_analisis_senior(pregunta, tasa_frontend)
    return jsonify({
        "respuesta_asistente": respuesta
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)