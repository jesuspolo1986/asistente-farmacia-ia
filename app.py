import os
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, render_template, session
from mistralai import Mistral
from datetime import datetime
import easyocr
from werkzeug.utils import secure_filename
from rapidfuzz import process, utils

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "farmacia_senior_2026")

# --- CONFIGURACIÓN DE CARPETAS ---
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CONFIGURACIÓN DE IA Y OCR ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

# Inicializamos el lector de OCR (Español)
# Nota: La primera vez descargará los modelos (~30MB)
reader = easyocr.Reader(['es']) 

df_inv = None

# --- LÓGICA DE APOYO ---

def buscar_producto_inteligente(texto_ocr, df_inventario):
    """Busca el nombre más parecido en el inventario para manejar letra de médico."""
    if df_inventario is None: return None
    
    # Extraemos los nombres de los productos del inventario
    # Buscamos en la columna 'Producto' (ya normalizada a Title Case)
    lista_productos = df_inventario['Producto'].tolist()
    
    # Buscamos la coincidencia más cercana
    resultado = process.extractOne(texto_ocr, lista_productos, processor=utils.default_process)
    
    if resultado and resultado[1] > 60:  # Confianza mínima del 60%
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
    if not file: 
        return jsonify({"error": "No hay archivo"}), 400
    
    try:
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df_inv = pd.read_excel(stream)
        else:
            df_inv = pd.read_csv(stream)

        # Normalización Senior de columnas
        df_inv.columns = [str(c).replace("_", " ").strip().title() for c in df_inv.columns]
        df_inv = df_inv.fillna("No disponible")
        
        return jsonify({"success": True, "columnas": list(df_inv.columns)})
    except Exception as e:
        return jsonify({"error": f"Error al procesar archivo: {str(e)}"}), 500

@app.route('/escanear-receta', methods=['POST'])
def escanear_receta():
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "Hola, soy Elena. Por favor, primero carga el archivo de inventario para poder ayudarte con los precios."})
    
    if 'receta' not in request.files:
        return jsonify({"respuesta_asistente": "No recibí ninguna imagen de la receta."})
    
    file = request.files['receta']
    if file.filename == '':
        return jsonify({"respuesta_asistente": "Nombre de archivo vacío."})

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # 1. Extraer texto con EasyOCR
        resultados = reader.readtext(filepath, detail=0)
        texto_extraido = " ".join(resultados)
        
        # 2. Aviso de Día de Gracia (Dato: 15 de Enero)
        aviso_gracia = " Nota: Tu suscripción venció ayer 14 de enero, hoy estás en tu día de gracia."

        # 3. Búsqueda con lógica difusa
        producto_detectado = buscar_producto_inteligente(texto_extraido, df_inv)

        if producto_detectado is not None:
            respuesta = (f"He analizado el récipe. Identifiqué {producto_detectado['Producto']}. "
                         f"El precio actual es de ${producto_detectado['Precio Venta']} y tenemos "
                         f"{producto_detectado['Stock Actual']} unidades disponibles."
                         + aviso_gracia)
        else:
            respuesta = "He leído el récipe pero no logro encontrar una coincidencia clara en el inventario. ¿Podrías decirme el nombre del medicamento?" + aviso_gracia

        return jsonify({"respuesta_asistente": respuesta})

    except Exception as e:
        return jsonify({"respuesta_asistente": f"Hubo un error técnico al leer la imagen: {str(e)}"})
    finally:
        # Limpieza: Borrar el archivo procesado para ahorrar espacio
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/preguntar/<nombre_completo>', methods=['GET'])
def preguntar_por_voz(nombre_completo):
    global df_inv
    if df_inv is None:
        return jsonify({"respuesta_asistente": "El inventario no está cargado."})
    
    try:
        resumen_inventario = df_inv.to_string(index=False)
        fecha_hoy = "2026-01-15" # Actualizado a hoy

        prompt_sistema = f"Eres Elena, asistente experta de farmacia de AI Pro Analyst. Hoy es {fecha_hoy}. " \
                         f"Inventario:\n{resumen_inventario}\n" \
                         "REGLAS:\n" \
                         "1. Sé breve y profesional.\n" \
                         "2. Usa la columna 'Vencimiento' para alertar sobre productos caducados.\n" \
                         "3. Menciona que hoy es día de gracia si preguntan por el estado del sistema."

        response = client.chat.complete(
            model="mistral-small",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": nombre_completo}
            ],
            temperature=0
        )
        
        respuesta = response.choices[0].message.content
        return jsonify({"respuesta_asistente": respuesta})

    except Exception as e:
        return jsonify({"respuesta_asistente": "No pude procesar tu consulta de voz en este momento."})

if __name__ == '__main__':
    # Usamos el puerto 8000 como pediste
    app.run(host='0.0.0.0', port=8000, debug=True)