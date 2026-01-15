import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from rapidfuzz import process, utils

app = Flask(__name__)

# Variable global para el inventario
df_inv = None

def buscar_producto(nombre_usuario):
    global df_inv
    if df_inv is None:
        return "Elena: Primero debes cargar el archivo de inventario."
    
    # Normalizar nombres de productos para la búsqueda
    lista_productos = df_inv['Producto'].astype(str).tolist()
    
    # Búsqueda difusa (encuentra coincidencias aunque haya errores de dedo)
    resultado = process.extractOne(nombre_usuario, lista_productos, processor=utils.default_process)
    
    if resultado and resultado[1] > 70:
        nombre_match = resultado[0]
        fila = df_inv[df_inv['Producto'] == nombre_match].iloc[0]
        precio = fila['Precio Venta']
        return f"Elena: El producto '{nombre_match}' tiene un costo de {precio} dólares."
    
    return f"Elena: No encontré el producto '{nombre_usuario}' en el inventario."

@app.route('/')
def index():
    # Asegúrate de tener el archivo index.html en una carpeta llamada 'templates'
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_inv
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No se recibió el archivo"}), 400
    
    try:
        # Leer Excel o CSV
        stream = io.BytesIO(file.read())
        if file.filename.endswith(('.xlsx', '.xls')):
            df_inv = pd.read_excel(stream)
        else:
            df_inv = pd.read_csv(stream)
            
        # Limpiar encabezados: Quitar espacios y poner formato Título
        df_inv.columns = [str(c).strip().title() for c in df_inv.columns]
        
        return jsonify({
            "success": True, 
            "mensaje": f"Inventario cargado con {len(df_inv)} productos."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    texto_usuario = data.get("pregunta", "")
    
    # Recordatorio del día de gracia (Hoy es 15 de enero)
    aviso_gracia = "\n(Elena: Recuerda que hoy es tu día de gracia de suscripción)."
    
    respuesta = buscar_producto(texto_usuario) + aviso_gracia
    
    return jsonify({"respuesta_asistente": respuesta})

if __name__ == '__main__':
    # Configuración de puerto para Koyeb
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)