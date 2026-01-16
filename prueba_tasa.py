import requests

def obtener_tasa_venezuela():
    print("🔄 Intentando conexión con servidor espejo (V2)...")
    try:
        # Usamos la API de Dolarito o una similar que es más permisiva
        url = "https://api.dolarito.com/api/frontend/quotations"
        
        # Agregamos un "User-Agent" para que parezca que entramos desde un navegador Chrome
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Buscamos específicamente la tasa del BCV dentro de la respuesta
            # Dolarito devuelve una lista de monitores
            tasa_bcv = data.get('oficial', {}).get('padi', {}).get('value', None)
            
            if not tasa_bcv:
                # Intento alternativo según la estructura de Dolarito
                tasa_bcv = data.get('bcv', {}).get('padi', {}).get('value')

            print(f"✅ Conexión exitosa!")
            print(f"💵 Tasa encontrada: {tasa_bcv} BS/USD")
            return tasa_bcv
        else:
            print(f"❌ Error del servidor: Código {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error de red: {e}")
        return None

if __name__ == "__main__":
    tasa = obtener_tasa_venezuela()
    if tasa:
        print(f"\nResultado final: {tasa} BS")
    else:
        print("\nEl servidor bloqueó la petición. Probaremos otro método si persiste.")