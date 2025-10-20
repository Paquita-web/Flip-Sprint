import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv

# Cargar variables de entorno (para la conexión MQTT)
load_dotenv()

# --- CONFIGURACIÓN CRÍTICA ---
# Coordenadas con Sergio (E2)
MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = "greendelivery/rubia/telemetry" # <--- ¡IMPORTANTE! COORDINAR CON SERGIO

# Umbrales del Negocio (Seguridad de la Carne)
TEMP_UMBRAL = 4.0      # Temp máxima permitida (°C)
CONSECUTIVE_EVENTS = 3 # Eventos malos seguidos para considerarlo ALERTA SOSTENIDA

# Diccionario Global para mantener la memoria del estado de cada envío
package_state = {} 

# --- FUNCIONES MQTT ---

def on_connect(client, userdata, flags, rc):
    """Callback que se ejecuta al conectar con el Broker."""
    if rc == 0:
        print("Conexión MQTT exitosa. Suscribiéndose...")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Fallo en la conexión MQTT. Código: {rc}")

def on_message(client, userdata, msg):
    """Callback que se ejecuta al recibir un mensaje."""
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        process_telemetry(data)
    except json.JSONDecodeError:
        print("Error: Mensaje JSON inválido.")
    except Exception as e:
        print(f"Error al procesar mensaje: {e}")

# --- LÓGICA DEL CEREBRO (ISSUE #4) ---

def process_telemetry(data):
    """Aplica la lógica de estado y umbrales a cada dato."""
    global package_state
    
    temp = data.get('temperatura', 99.9) # Asegúrate de que la clave coincide con Sergio (E2)
    package_id = data.get('id_paquete', 'N/A')
    
    # 1. ¿El evento actual es malo?
    is_alert_event = temp > TEMP_UMBRAL
    
    # Inicializar el contador del paquete si es nuevo
    if package_id not in package_state:
        package_state[package_id] = 0

    if is_alert_event:
        # 2. El evento es malo, incrementamos el contador
        package_state[package_id] += 1
        
        if package_state[package_id] >= CONSECUTIVE_EVENTS:
            # 3. ¡ALERTA CRÍTICA SOSTENIDA!
            print(f"🚨🚨 ALERTA CRÍTICA: {package_id} - Temp {temp}°C SOSTENIDA.")
            # TODO: Aquí irá la llamada al webhook de Slack/Discord
        else:
            # Es un pico, pero no una alarma real aún
            print(f"🌡️ Advertencia: Pico temporal. Contador: {package_state[package_id]}/{CONSECUTIVE_EVENTS}")
            
    else:
        # 4. El dato es bueno, reseteamos el contador
        if package_state[package_id] > 0:
            print(f"🟢 Reseteando alerta de {package_id}. Volvió a la normalidad.")
        package_state[package_id] = 0 
        
    # TODO: En el ISSUE #5, esta función llamará a send_to_ingest_api(data)

# --- INICIO DEL SERVICIO ---
if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Procesador: Intentando conectar a {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"Error fatal de conexión: {e}")
