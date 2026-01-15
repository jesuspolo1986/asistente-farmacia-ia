import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from flask import Flask, request, jsonify, render_template
from mistralai import Mistral
from werkzeug.utils import secure_filename
from rapidfuzz import process, utils

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_2026")

# --- CONFIGURACIÓN ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Token de Mistral desde variables de entorno
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

df_inv = None

def encode_image(image_path):
    """Codifica la imagen para enviarla a la API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def buscar_producto_inteligente(texto_ocr, df_inventario):
    """Busca el medicamento en el Excel usando lógica difusa."""
    if df_inventario is None or not texto_ocr: return None
    lista_productos = df_inventario['Producto'].tolist()
    res = process.extractOne(texto_ocr, lista_productos, processor=utils.default_process)
    if res and res[1] > 60:
        return df_inventario[df_inventario['Producto'] == res[0]].iloc[0]
    return None

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
        df_inv.columns = [str(c).replace("_", " ").strip().title() for c in df_inv.columns]
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/escanear-receta', methods=['POST'])
def escanear_receta():
    global df_inv
    if df_inv is None: return jsonify({"respuesta_asistente": "Sube el inventario primero."})
    
    file = request.files.get('receta')
    if not file: return jsonify({"respuesta_asistente": "No recibí la imagen."})
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # 1. Visión con Mistral (Pixtral)
        b64_img = encode_image(filepath)
        vision_res = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Dime solo el nombre del medicamento en esta receta. Sin explicaciones."},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64_img}"}
                ]
            }]
        )
        texto_extraido = vision_res.choices[0].message.content.strip()

        # 2. Lógica de Negocio y Día de Gracia
        aviso = " Nota: Tu suscripción venció ayer 14 de enero, hoy estás en día de gracia."
        prod = buscar_producto_inteligente(texto_extraido, df_inv)

        if prod is not None:
            msg = f"Elena detectó {prod['Producto']}. Precio: ${prod['Precio Venta']}. Stock: {prod['Stock Actual']}." + aviso
        else:
            msg = f"Leí '{texto_extraido}', pero no está en el inventario." + aviso
        return jsonify({"respuesta_asistente": msg})
    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error de Visión: {str(e)}"})
    finally:
        if os.path.exists(filepath): os.remove(filepath)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)