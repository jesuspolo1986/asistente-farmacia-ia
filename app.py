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
    if inventario["df"] is None: return "Elena: Sincronice el archivo primero."
    
    df = inventario["df"].copy() # Trabajamos sobre una copia
    tasa = float(tasa_recibida)
    p_limpia = pregunta_original.lower()
    rubro = inventario.get("rubro", "General")
    hoy = datetime.now()

    # --- 1. NORMALIZACIÓN DE EMERGENCIA (El "Sabelotodo") ---
    mapeo_emergencia = {
        'Producto': ['sku', 'empleado', 'ruta', 'articulo', 'item', 'nombre'],
        'Total': ['ventas_netas', 'monto', 'subtotal', 'ingresos', 'sueldo'],
        'Vendedor': ['conductor', 'asesor', 'ejecutivo', 'nombre_vendedor']
    }
    
    for estandar, sinonimos in mapeo_emergencia.items():
        if estandar not in df.columns:
            for col in df.columns:
                if col.lower() in sinonimos:
                    df.rename(columns={col: estandar}, inplace=True)
                    break

    # --- 2. CÁLCULO PROACTIVO (Si no hay Total, lo creamos) ---
    if 'Total' not in df.columns and 'Cantidad' in df.columns and 'Precio_Unitario' in df.columns:
        df['Total'] = df['Cantidad'] * df['Precio_Unitario']

    # ==========================================================
    # LÓGICA DE RESPUESTA SENIOR
    # ==========================================================
    if modo_admin:
        # Análisis de Rendimiento (Vendedores/Conductores/Empleados)
        if any(p in p_limpia for p in ["vendedor", "quién", "mejor", "conductor", "desempeño"]):
            col_target = 'Vendedor' if 'Vendedor' in df.columns else None
            if col_target and 'Total' in df.columns:
                stats = df.groupby(col_target)['Total'].sum().sort_values(ascending=False)
                return f"Análisis Senior: El líder de gestión es {stats.index[0]} con un impacto de ${stats.iloc[0]:,.2f}."
            
        # Análisis de Pareto / Estrella
        if any(p in p_limpia for p in ["rentable", "pareto", "estrella", "más vendido"]):
            col_valor = 'Total' if 'Total' in df.columns else ('Precio Venta' if 'Precio Venta' in df.columns else df.columns[-1])
            pareto = df.groupby('Producto')[col_valor].sum().sort_values(ascending=False)
            return f"El activo estrella en {rubro} es {pareto.index[0]} con un valor acumulado de ${pareto.iloc[0]:,.2f}."

    # ==========================================================
    # BÚSQUEDA UNIVERSAL (Si nada de lo anterior aplica)
    # ==========================================================
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(limpiar_pregunta(pregunta_original), productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        # Si es farmacia y pides precio
        if 'Precio Venta' in df.columns:
            p_usd = float(fila['Precio Venta'])
            return f"El {match[0]} tiene un costo de {p_usd * tasa:,.2f} BS ({p_usd:,.2f} USD)."
        # Si es RRHH o Logística
        if 'Total' in df.columns:
            return f"Registro encontrado: {match[0]} con un valor/sueldo de ${fila['Total']:,.2f}."

    return f"Como tu consultora en {rubro}, no hallé el dato exacto, pero puedo analizar tus totales o el mejor desempeño si lo deseas."
@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        # Mapeo Inteligente
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
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error", 400
    df = inventario["df"]
    hoy = datetime.now()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"REPORTE DE {inventario['rubro'].upper()}", ln=True, align='C')
    
    # Lógica de PDF... (Abreviada para el mensaje, pero completa en tu archivo)
    pdf.set_font("Arial", '', 12)
    pdf.ln(10)
    pdf.cell(190, 10, f"Generado por Elena AI el {hoy.strftime('%d/%m/%Y')}", ln=True)
    
    output = io.BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Reporte_Elena.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))