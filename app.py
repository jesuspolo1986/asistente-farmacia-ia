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
    if inventario["df"] is None: return "Elena: Por favor, sincronice el inventario primero."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    df = inventario["df"]
    rubro = inventario["rubro"]
    p_limpia = pregunta_original.lower()
    hoy = datetime.now()

    # ==========================================================
    # LÓGICA ESTRATÉGICA (SOLO MODO ADMINISTRATIVO)
    # ==========================================================
    if modo_admin:
        # 1. Comandos de AI Pro Analyst (Ventas)
        if any(p in p_limpia for p in ["vendedor", "promedio", "quién vendió"]):
            if 'Vendedor' in df.columns:
                stats = df.groupby('Vendedor')['Total'].agg(['mean', 'sum', 'count']).sort_values(by='sum', ascending=False)
                top_v = stats.index[0]
                return f"Líder en ventas: {top_v} con ${stats.loc[top_v, 'sum']:,.2f}. Promedio: ${stats.loc[top_v, 'mean']:,.2f}."
            return "Este archivo no contiene datos de vendedores."

        # 2. Análisis de Pareto / Rentabilidad
        if any(p in p_limpia for p in ["rentable", "pareto", "estrella"]):
            col_v = 'Total' if 'Total' in df.columns else 'Precio Venta'
            pareto = df.groupby('Producto')[col_v].sum().sort_values(ascending=False)
            return f"El producto estrella de tu {rubro} es {pareto.index[0]} (${pareto.iloc[0]:,.2f})."

        # 3. Comandos de Farmacia (Vencidos)
        if "vencido" in p_limpia:
            vencidos_df = df[pd.to_datetime(df['Vencimiento']) < hoy]
            if vencidos_df.empty: return "Excelente, no hay productos vencidos."
            lista = ", ".join(vencidos_df['Producto'].head(5).tolist())
            return f"Alerta Sanitaria en {rubro}: Tenemos vencidos como {lista}."

        # 4. Faltantes e Inversión
        if any(x in p_limpia for x in ["falta", "stock bajo", "invertir", "comprar"]):
            faltantes_df = df[df['Stock Actual'] <= df['Stock Mínimo']].copy()
            if faltantes_df.empty: return "El stock está en niveles óptimos."
            faltantes_df['Diferencia'] = faltantes_df['Stock Mínimo'] - faltantes_df['Stock Actual']
            inv_usd = (faltantes_df['Diferencia'] * faltantes_df['Costo']).sum()
            return f"Atención: Faltan {len(faltantes_df)} items. Inversión necesaria: {inv_usd:,.2f} USD."

    # ==========================================================
    # BÚSQUEDA DE PRODUCTO (UNIVERSAL)
    # ==========================================================
    prod_buscado = limpiar_pregunta(pregunta_original)
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(prod_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        p_usd = float(fila['Precio Venta'])
        p_bs = p_usd * tasa
        
        if not modo_admin:
            return f"El valor de {match[0]} es {p_bs:,.2f} BS ({p_usd:,.2f} USD)."
        else:
            costo = float(fila['Costo'])
            margen = ((p_usd - costo) / p_usd) * 100
            return f"Auditoría {match[0]}: Stock {fila['Stock Actual']}. Margen {margen:.1f}%. Rubro: {rubro}."

    return f"No encontré el producto, pero como tu asistente de {rubro} puedo analizar tu gestión general."

# --- RUTAS FLASK ---

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