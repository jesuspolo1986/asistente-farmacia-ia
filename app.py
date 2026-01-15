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
    frases = ["cuanto cuesta", "dame el precio de", "reporte de", "estatus de", "analisis de"]
    for f in frases: texto = texto.replace(f, "")
    return texto.strip()

def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: return "Elena: Inventario no cargado."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    producto_buscado = limpiar_pregunta(pregunta_original)
    
    df = inventario["df"]
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        costo_usd = float(fila['Costo'])
        stock = int(fila['Stock Actual'])
        minimo = int(fila['Stock Mínimo'])

        # 1. LÓGICA DE PARETO (Valor de Inventario)
        df['Valor_Inv'] = df['Stock Actual'] * df['Precio Venta']
        umbral_pareto = df['Valor_Inv'].quantile(0.8) # El 20% superior
        es_pareto = "⭐ PRODUCTO CLAVE (Pareto A)" if (stock * precio_usd) >= umbral_pareto else "Producto Clase B/C"

        # 2. PREDICCIÓN Y ALERTAS
        venc_str = str(fila['Vencimiento'])
        vencido = datetime.strptime(venc_str, '%Y-%m-%d') < datetime.now()
        margen = ((precio_usd - costo_usd) / precio_usd) * 100

        if not modo_admin:
            if vencido: return f"El activo {match[0]} está en revisión técnica y no disponible."
            return f"El valor de {match[0]} es {precio_bs:,.2f} BS ({precio_usd} USD). ¿Desea factura?"

        else:
            # RECOMENDACIONES PREDICTIVAS
            rec = ""
            if stock <= minimo:
                rec = "⚠️ ACCIÓN: Reponer de inmediato, alta probabilidad de quiebre. "
            elif margen < 20:
                rec = "📉 CONSEJO: Margen crítico. Evaluar cambio de proveedor. "
            elif stock > (minimo * 4):
                rec = "📦 SOBRE-STOCK: Evaluar promoción para liberar capital. "
            
            if vencido: rec = "❌ RETIRAR: Pérdida total por vencimiento. "

            return (f"AUDITORÍA SENIOR: {match[0]} ({es_pareto}). "
                    f"Margen: {margen:.1f}%. Stock: {stock}. "
                    f"Ubicación: {fila['Ubicación']}. "
                    f"PREDICCIÓN: {rec}")
    
    return "Producto no localizado."

# ... (Rutas de upload y preguntar se mantienen igual que las anteriores) ...

@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No file"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        df.columns = [str(c).strip().title() for c in df.columns]
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Inteligencia de Negocios Activa."})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 55.4), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))