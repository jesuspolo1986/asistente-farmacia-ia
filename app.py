import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)
# Memoria de trabajo
inventario = {"df": None, "tasa": 55.40}

def limpiar_pregunta(texto):
    texto = texto.lower()
    frases = ["cuanto cuesta", "dame el precio de", "reporte de", "estatus de", "analisis de", "precio del"]
    for f in frases: texto = texto.replace(f, "")
    return texto.strip()
def buscar_analisis_senior(pregunta_original, tasa_recibida, modo_admin=False):
    if inventario["df"] is None: 
        return "Elena: Por favor, sincronice el inventario primero."
    
    tasa = float(tasa_recibida)
    inventario["tasa"] = tasa 
    pregunta_limpia = pregunta_original.lower()
    df = inventario["df"]
    hoy = datetime.now()

    # ==========================================================
    # LÓGICA ESTRATÉGICA (SOLO MODO ADMINISTRATIVO)
    # ==========================================================
    if modo_admin:
        # 1. Comando para VENDEDORES / TICKET PROMEDIO (AI Pro Analyst)
        if any(p in pregunta_limpia for p in ["vendedor", "promedio", "quién vendió"]):
            if 'Vendedor' not in df.columns: return "No encuentro la columna de Vendedores en este archivo."
            stats = df.groupby('Vendedor')['Total'].agg(['mean', 'sum', 'count']).sort_values(by='sum', ascending=False)
            top_v = stats.index[0]
            return (f"Análisis listo. El líder es {top_v} con ${stats.loc[top_v, 'sum']:,.2f} vendidos. "
                    f"Su ticket promedio es de ${stats.loc[top_v, 'mean']:,.2f}.")

        # 2. Comando para PRODUCTO ESTRELLA / PARETO (AI Pro Analyst)
        if any(p in pregunta_limpia for p in ["rentable", "pareto", "estrella", "más vendido"]):
            # Si es archivo de ventas (tiene columna Total), si no, usamos Valor de Inventario
            col_valor = 'Total' if 'Total' in df.columns else 'Precio Venta'
            pareto = df.groupby('Producto')[col_valor].sum().sort_values(ascending=False)
            top_p = pareto.index[0]
            return f"El producto estrella es {top_p}, con un valor total de ${pareto.iloc[0]:,.2f}."

        # 3. Comando para VENCIDOS (Farmacia)
        if "vencido" in pregunta_limpia or "vencidos" in pregunta_limpia:
            vencidos_df = df[pd.to_datetime(df['Vencimiento']) < hoy]
            if vencidos_df.empty: return "Excelente, no hay productos vencidos."
            lista = ", ".join(vencidos_df['Producto'].head(5).tolist())
            return f"Alerta: Tenemos productos vencidos como: {lista}."

        # 4. Comando para FALTANTES / INVERSIÓN (Farmacia)
        if any(palabra in pregunta_limpia for palabra in ["falta", "stock bajo", "reposición", "comprar", "invertir", "agotarse"]):
            faltantes_df = df[df['Stock Actual'] <= df['Stock Mínimo']].copy()
            if faltantes_df.empty: return "Niveles de stock óptimos."
            faltantes_df['Diferencia'] = faltantes_df['Stock Mínimo'] - faltantes_df['Stock Actual']
            inv_usd = (faltantes_df['Diferencia'] * faltantes_df['Costo']).sum()
            return f"Atención: Faltan {len(faltantes_df)} productos. Inversión necesaria: {inv_usd:,.2f} USD."

    # ==========================================================
    # BÚSQUEDA DE PRODUCTO INDIVIDUAL (PÚBLICO Y ADMIN)
    # ==========================================================
    producto_buscado = limpiar_pregunta(pregunta_original)
    productos = df['Producto'].astype(str).tolist()
    match = process.extractOne(producto_buscado, productos, processor=utils.default_process)
    
    if match and match[1] > 60:
        fila = df[df['Producto'] == match[0]].iloc[0]
        precio_usd = float(fila['Precio Venta'])
        precio_bs = precio_usd * tasa
        
        if not modo_admin:
            # Respuesta rápida para cliente
            return f"El valor de {match[0]} es {precio_bs:,.2f} BS ({precio_usd:,.2f} USD)."
        else:
            # Respuesta detallada para el dueño
            costo = float(fila['Costo'])
            margen = ((precio_usd - costo) / precio_usd) * 100
            return f"Auditoría de {match[0]}: Precio {precio_usd} USD, Costo {costo} USD. Margen: {margen:.1f}%. Stock: {fila['Stock Actual']}."

    return "No logré identificar el producto o el comando de auditoría."gré identificar el comando estratégico. Prueba con: '¿Quién es el mejor vendedor?' o '¿Cuál es el producto más rentable?'"
@app.route('/')
def index(): return render_template('index.html', tasa=inventario["tasa"])

# Diccionario de Sinónimos para columnas
MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item', 'desc'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_venta', 'v. unitario'],
    'Costo': ['costo', 'precio costo', 'costo_u', 'compra', 'p. costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia', 'cant'],
    'Stock Mínimo': ['stock mínimo', 'minimo', 'stock_min', 'alerta', 'mínimo'],
    'Vencimiento': ['vencimiento', 'fecha_venc', 'vence', 'expiracion', 'f_vencimiento'],
    'Ubicación': ['ubicación', 'estante', 'pasillo', 'localizacion', 'donde']
}

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"error": "No hay archivo"}), 400
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        # --- LÓGICA DE DETECCIÓN INTELIGENTE ---
        columnas_reales = {col: str(col).strip().lower() for col in df.columns}
        nuevas_columnas = {}

        for estandar, sinonimos in MAPEO_COLUMNAS.items():
            for col_real, col_limpia in columnas_reales.items():
                if col_limpia in sinonimos:
                    nuevas_columnas[col_real] = estandar
                    break
        
        # Renombramos solo las que encontramos
        df.rename(columns=nuevas_columnas, inplace=True)
        
        # Verificación de seguridad
        faltantes = [c for c in ["Producto", "Precio Venta", "Costo", "Stock Actual"] if c not in df.columns]
        if faltantes:
            return jsonify({"error": f"Faltan columnas críticas o no reconocidas: {', '.join(faltantes)}"}), 400

        # Limpieza de datos
        df['Vencimiento'] = pd.to_datetime(df['Vencimiento']).dt.strftime('%Y-%m-%d')
        inventario["df"] = df
        return jsonify({"success": True, "mensaje": "Base de datos sincronizada con éxito. Elena reconoce todas las columnas."})
        
    except Exception as e: return jsonify({"error": f"Error al leer el archivo: {str(e)}"}), 500
@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis_senior(data.get("pregunta", ""), data.get("tasa", 55.4), data.get("modo_admin", False))
    return jsonify({"respuesta_asistente": resp})

@app.route('/descargar-pdf', methods=['GET'])
def descargar_pdf():
    if inventario["df"] is None: return "Error", 400
    df = inventario["df"]
    hoy = datetime.now()
    faltantes = df[df['Stock Actual'] <= df['Stock Mínimo']]
    vencidos = df[pd.to_datetime(df['Vencimiento']) < hoy]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "REPORTE DE GERENCIA - ELENA AI", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Fecha: {hoy.strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "PRODUCTOS PARA REPOSICIÓN", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, f in faltantes.iterrows():
        pdf.cell(190, 7, f"- {f['Producto']}: {f['Stock Actual']} unidades (Mín: {f['Stock Mínimo']})", ln=True)
    
    pdf.ln(5)
    pdf.set_fill_color(255, 200, 200)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, "PRODUCTOS VENCIDOS", ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    for _, v in vencidos.iterrows():
        pdf.cell(190, 7, f"- {v['Producto']}: Vencido el {v['Vencimiento']}", ln=True)

    output = io.BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="Reporte_Cierre.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))