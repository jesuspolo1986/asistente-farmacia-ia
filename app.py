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
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_senior_2026")

# --- CONFIGURACIÓN ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

df_inv = None

# --- FUNCIONES DE APOYO ---

def encode_image(image_path):
    """Codifica la imagen a base64 para la API de Visión."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def buscar_producto_inteligente(texto_ocr, df_inventario):
    """Fuzzy matching para encontrar el producto en el Excel cargado."""
    if df_inventario is None or not texto_ocr: return None
    lista_productos = df_inventario['Producto'].tolist()
    resultado = process.extractOne(texto_ocr, lista_productos, processor=utils.default_process)
    
    if resultado and resultado[1] > 60:
        nombre_encontrado = resultado[0]
        return df_inventario[df_inventario['Producto'] == nombre_encontrado].iloc[0]
    return None

# --- RUTAS ---

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
        df_inv = df_inv.fillna("No disponible")
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/escanear-receta', methods=['POST'])
def escanear_receta():
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Hola, soy Elena. Por favor, sube primero el inventario."})
    
    if 'receta' not in request.files:
        return jsonify({"respuesta_asistente": "No se recibió la imagen."})
    
    file = request.files['receta']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # 1. Codificar y Enviar a Mistral Vision
        base64_image = encode_image(filepath)
        
        # Usamos Pixtral para leer la receta
        vision_response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Dime solo el nombre del medicamento principal que aparece en esta receta médica. No des explicaciones, solo el nombre."},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                    ]
                }
            ]
        )
        
        texto_extraido = vision_response.choices[0].message.content.strip()
        
        # 2. Lógica de negocio y Día de Gracia (15 de enero)
        aviso_gracia = " Recuerda: Tu suscripción venció ayer 14, hoy estás en día de gracia."
        producto = buscar_producto_inteligente(texto_extraido, df_inv)

        if producto is not None:
            respuesta = (f"Elena detectó {producto['Producto']}. "
                         f"Precio: ${producto['Precio Venta']}. "
                         f"Ubicación: {producto['Ubicación']}." + aviso_gracia)
        else:
            respuesta = f"Leí '{texto_extraido}', pero no está en el inventario." + aviso_gracia

        return jsonify({"respuesta_asistente": respuesta})

    except Exception as e:
        return jsonify({"respuesta_asistente": f"Error de Visión: {str(e)}"})
    finally:
        if os.path.exists(filepath): os.remove(filepath)

@app.route('/preguntar/<consulta>', methods=['GET'])
def preguntar_por_voz(consulta):
    if df_inv is None: return jsonify({"respuesta_asistente": "Sube el inventario primero."})
    
    try:
        resumen = df_inv.to_string(index=False)
        prompt = f"Eres Elena, asistente de farmacia. Hoy es 2026-01-15. Inventario:\n{resumen}"
        
        response = client.chat.complete(
            model="mistral-small",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": consulta}]
        )
        return jsonify({"respuesta_asistente": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"respuesta_asistente": "Error de consulta."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)