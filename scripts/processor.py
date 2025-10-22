import requests
import paho.mqtt.client as mqtt
import json
import time
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# --- CONFIGURACIÓN CRÍTICA ---
MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = "greendelivery/rubia/telemetry" # Coordinar con Sergio (E2)

# --- CONFIGURACIÓN DE RESILIENCIA (ISSUE #5) ---
# Lee la URL que definiste en docker-compose (ej: http://alonso-api:8000/ingest)
API_INGEST_URL = os.getenv("API_INGEST_URL", "http://localhost:8000/ingest") 
MAX_RETRIES = 5 

# Umbrales del Negocio (Seguridad de la Carne)
TEMP_UMBRAL = 4.0      
CONSECUTIVE_EVENTS = 3 

# Diccionario Global para mantener la memoria del estado de cada envío
package_state = {}

# --- FUNCIÓN DE RESILIENCIA (ISSUE #5) ---

def send_to_ingest_api(data, max_retries=MAX_RETRIES):
    """Implementa la Resiliencia: Envía datos a la API con reintentos y backoff."""
    retries = 0
    while retries < max_retries:
        try:
            # Petición POST a la API de Alonso (E1)
            response = requests.post(API_INGEST_URL, json=data, timeout=5)
            # Lanza excepción para códigos de error (4xx o 5xx)
            response.raise_for_status() 

            print(f"🟢 Éxito: Dato {data.get('id_paquete')} insertado correctamente.")
            return # Salir del bucle, la inserción fue exitosa
            
        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"❌ Fallo de API/Red (Intento {retries}/{max_retries}): {e}")

            if retries < max_retries:
                # Retardo Exponencial (Backoff): el tiempo de espera crece (2s, 4s, 8s, 16s...)
                wait_time = 2 ** retries 
                print(f"⏳ Reintentando en {wait_time} segundos...")
                time.sleep(wait_time) 
            else:
                # Agotó los intentos: registra como fallo crítico
                print(f"❌❌ FALLO CRÍTICO: Se agotaron los reintentos. Dato {data.get('id_paquete')} perdido.")


# --- LÓGICA DEL CEREBRO (ISSUE #4 INTEGRADO CON #5) ---

def process_telemetry(data):
    """Aplica la lógica de estado y umbrales a cada dato."""
    global package_state

    temp = data.get('temperatura', 99.9) 
    package_id = data.get('id_paquete', 'N/A')

    # 1. ¿El evento actual es malo?
    is_alert_event = temp > TEMP_UMBRAL

    if package_id not in package_state:
        package_state[package_id] = 0

    if is_alert_event:
        package_state[package_id] += 1
        
        if package_state[package_id] >= CONSECUTIVE_EVENTS:
            # ALERTA CRÍTICA SOSTENIDA
            print(f"🚨🚨 ALERTA CRÍTICA: {package_id} - Temp {temp}°C SOSTENIDA.")
            # TODO: Aquí irá la llamada al webhook (extra a este Issue)
        else:
            # Pico temporal
            print(f"🌡️ Advertencia: Pico temporal. Contador: {package_state[package_id]}/{CONSECUTIVE_EVENTS}")
            
    else:
        # Dato bueno, reseteamos el contador
        if package_state[package_id] > 0:
            print(f"🟢 Reseteando alerta de {package_id}. Volvió a la normalidad.")
        package_state[package_id] = 0

    # ⬇️ TAREA DEL ISSUE #5: Llamar a la función de envío resiliente
    send_to_ingest_api(data)


# --- FUNCIONES MQTT (Sin cambios) ---

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


# --- INICIO DEL SERVICIO (Sin cambios) ---
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


