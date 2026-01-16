import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)

# --- MEMORIA DE TRABAJO ---
inventario = {"df": None, "tasa": 325.40, "rubro": "General"}

# --- CONFIGURACIÓN UNIVERSAL (SINÓNIMOS) ---
MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item', 'desc', 'modelo'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario', 'p.unitario'],
    'Costo': ['costo', 'compra', 'p.costo', 'costo_u'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia', 'cant', 'disponible'],
    'Stock Mínimo': ['stock mínimo', 'minimo', 'alerta', 'mínimo', 'reorden'],
    'Vencimiento': ['vencimiento', 'vence', 'expiracion', 'f_vencimiento', 'fecha_venc'],
    'Vendedor': ['vendedor', 'ejecutivo', 'asesor', 'empleado'],
    'Total': ['total', 'subtotal', 'monto_venta', 'monto'],
    'Ubicación': ['ubicación', 'estante', 'pasillo', 'localizacion', 'donde']
}

def detectar_rubro(df):
    cols = [str(c).lower() for c in df.columns]
    if any(p in " ".join(cols) for p in ['vencimiento', 'mg', 'lote', 'sanitario']): return "Farmacia"
    if any(p in " ".join(cols) for p in ['talla', 'color', 'talle', 'marca']): return "Ropa/Calzado"
    if any(p in " ".join(cols) for p in ['vendedor', 'total', 'cliente']): return "Ventas/Gerencia"
    return "Comercio General"

def limpiar_pregunta(texto):
    texto = texto.lower()
    frases = ["cuanto cuesta", "dame el precio de", "reporte de", "estatus de", "analisis de", "precio del"]
    for f in frases: texto = texto.replace(f, "")
    return texto.strip()

# --- MOTOR DE INTELIGENCIA FUSIONADO ---
def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: 
        return "Elena: Por favor, sincronice el inventario de la farmacia primero."
    
    df = inventario["df"]
    tasa = float(tasa_recibida)
    p_limpia = pregunta_original.lower()
    hoy = datetime.now()

    if modo_admin:
        # 1. Alerta de Vencidos
        if any(x in p_limpia for x in ["vencido", "caducado", "vence", "auditar"]):
            vencidos = df[pd.to_datetime(df['Vencimiento'], errors='coerce') < hoy]
            if vencidos.empty: 
                return "Auditoría completada: No existen productos vencidos en los estantes."
            perdida = (vencidos['Stock Actual'] * vencidos['Costo']).sum()
            lista = ", ".join(vencidos['Producto'].head(5).tolist())
            return (f"¡Alerta de Gestión! Tenemos {len(vencidos)} productos vencidos (ej: {lista}). "
                    f"Esto representa una pérdida de ${perdida:,.2f}.")

        # 2. Análisis de Reposición
        if any(x in p_limpia for x in ["falta", "comprar", "invertir", "stock bajo", "pedido"]):
            faltantes = df[df['Stock Actual'] <= df['Stock Mínimo']].copy()
            if faltantes.empty: return "El inventario está full."
            faltantes['Faltante'] = faltantes['Stock Mínimo'] - faltantes['Stock Actual']
            inv_usd = (faltantes['Faltante'] * faltantes['Costo']).sum()
            return f"Informe: Faltan {len(faltantes)} items. Inversión: ${inv_usd:,.2f} USD."

    # MODO USUARIO
    prod_buscado = limpiar_pregunta(pregunta_original)
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(prod_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        p_usd = float(fila['Precio Venta'])
        stock = int(fila['Stock Actual'])
        if stock <= 0: return f"El producto {match[0]} está agotado."
        return f"El {match[0]} cuesta {p_usd * tasa:,.2f} BS (${p_usd:,.2f} USD). Stock: {stock}."

    return "No encontré ese medicamento."

# --- RUTAS FLASK (CORREGIDAS) ---

@app.route('/')
def index(): 
    return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        # Normalizar nombres de columnas
        columnas_reales = {col: str(col).strip().lower() for col in df.columns}
        nuevas_cols = {}
        for estandar, sinonimos in MAPEO_COLUMNAS.items():
            for col_real, col_limpia in columnas_reales.items():
                if col_limpia in sinonimos:
                    nuevas_cols[col_real] = estandar
                    break
        df.rename(columns=nuevas_cols, inplace=True)
        
        inventario["rubro"] = detectar_rubro(df)
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": f"Sincronizado: Rubro {inventario['rubro']}"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)