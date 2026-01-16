import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from rapidfuzz import process, utils
from datetime import datetime

app = Flask(__name__)

# --- MEMORIA GLOBAL PERSISTENTE ---
# Mientras el servidor en Koyeb esté encendido, todos los usuarios ven estos mismos datos
inventario = {
    "df": None, 
    "tasa": 325.40, 
    "ultima_actualizacion": "No sincronizado"
}

MAPEO_COLUMNAS = {
    'Producto': ['producto', 'descripcion', 'nombre', 'articulo', 'item'],
    'Precio Venta': ['precio venta', 'pvp', 'precio', 'venta', 'precio_unitario'],
    'Costo': ['costo', 'compra', 'p.costo'],
    'Stock Actual': ['stock actual', 'stock', 'cantidad', 'existencia'],
    'Vencimiento': ['vencimiento', 'vence', 'expiracion']
}

def buscar_analisis(pregunta, tasa, modo_admin):
    if inventario["df"] is None: return "Elena: Esperando carga de inventario desde gerencia."
    
    df = inventario["df"]
    p_limpia = pregunta.lower().replace("precio", "").replace("dame el", "").strip()
    
    match = process.extractOne(p_limpia, df['Producto'].astype(str).tolist(), processor=utils.default_process)
    
    if match and match[1] > 60:
        f = df[df['Producto'] == match[0]].iloc[0]
        precio_bs = f['Precio Venta'] * float(tasa)
        
        if modo_admin:
            # Info sensible para el dueño/gerente
            m = ((f['Precio Venta'] - f['Costo']) / f['Precio Venta']) * 100 if f['Precio Venta'] > 0 else 0
            return (f"📊 {match[0]} | Costo: ${f['Costo']:.2f} | Venta: ${f['Precio Venta']:.2f} | "
                    f"Margen: {m:.1f}% | Stock: {int(f['Stock Actual'])}")
        
        # Info pública para vendedores
        return f"El {match[0]} cuesta {precio_bs:,.2f} BS (${f['Precio Venta']:,.2f} USD). Stock: {int(f['Stock Actual'])}."

    return "Lo siento, no encuentro ese producto en el inventario."

@app.route('/')
def terminal_ventas():
    # URL para los empleados (Aura Azul)
    return render_template('index.html', modo="vendedor", tasa=inventario["tasa"])

@app.route('/gerencia-farmacia-2026') # URL SECRETA PARA EL DUEÑO
def terminal_gerencia():
    # URL para la oficina (Aura Púrpura)
    return render_template('index.html', modo="admin", tasa=inventario["tasa"])

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return jsonify({"success": False})
    try:
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(stream)
        
        nuevas = {c: est for est, sin in MAPEO_COLUMNAS.items() for c in df.columns if str(c).lower().strip() in sin}
        df.rename(columns=nuevas, inplace=True)
        
        inventario["df"] = df
        inventario["ultima_actualizacion"] = datetime.now().strftime("%H:%M:%S")
        return jsonify({"success": True, "mensaje": f"Inventario actualizado a las {inventario['ultima_actualizacion']}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/preguntar', methods=['POST'])
def preguntar():
    data = request.json
    resp = buscar_analisis(data.get("pregunta", ""), data.get("tasa", 325.40), data.get("modo_admin", False))
    return jsonify({"respuesta": resp})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))