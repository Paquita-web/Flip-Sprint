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
MQTT_TOPIC = "greendelivery/rubia/telemetry"

# --- CONFIGURACIÓN DE RESILIENCIA Y ACCIÓN (Cap. 5 & 4) ---
API_INGEST_URL = os.getenv("API_INGEST_URL", "http://alonso-api:8000/ingest")
DISCORD_WEBHOOK_TEMP = os.getenv("DISCORD_WEBHOOK_TEMP") # Webhook para #sensor-temperatura
DISCORD_WEBHOOK_DOOR = os.getenv("DISCORD_WEBHOOK_DOOR") # Webhook para #sensor-puerta
MAX_RETRIES = 5

# --- Umbrales del Negocio (Cap. 3) ---
TEMP_UMBRAL = 8.0  # El enunciado original pide > 8.0°C
G_FORCE_UMBRAL = float(os.getenv("G_FORCE_UMBRAL", 2.5)) # Añadido G-Force desde .env
CONSECUTIVE_EVENTS = 3 # Lógica Stateful: Sostenida durante N eventos

# Diccionario Global para mantener la memoria del estado de cada envío
# Estado: {'consecutive': int, 'is_alerting_temp': bool, 'is_alerting_door': bool}
package_state = {}


# --- FUNCIONES DE ACCIÓN (Discord Webhooks) ---

def send_discord_alert(data, reason, webhook_url):
    """Envía un mensaje de alerta a Discord usando el Webhook específico."""
    if not webhook_url:
        print(f"❌ ERROR: URL de Discord para {reason} no configurada. Alerta no enviada.")
        return

    # Definir propiedades visuales según la razón
    if "Temperatura" in reason:
        color_code = 16711680  # Rojo
        alert_title = "🌡️ ALERTA CRÍTICA DE TEMPERATURA"
    elif "Puerta Abierta" in reason:
        color_code = 16776960  # Amarillo
        alert_title = "🚪 ALERTA OPERACIONAL DE PUERTA"
    else:
        color_code = 65535 # Azul
        alert_title = "🚨 ALERTA GENERAL"

    # Construcción del payload JSON para Discord (Embed)
    payload = {
        "content": "@here",
        "embeds": [{
            "title": f"{alert_title}: {data.get('id_paquete')}",
            "description": f"Razón: **{reason}**.\nRevisión inmediata requerida.",
            "color": color_code,
            "fields": [
                {"name": "Temperatura", "value": f"{data.get('temperatura', 'N/A')} °C", "inline": True},
                {"name": "Puerta Abierta", "value": str(data.get('puerta_abierta', 'N/A')), "inline": True},
                {"name": "Fuerza G", "value": f"{data.get('fuerza_g', 'N/A')} G", "inline": False},
                {"name": "Timestamp", "value": data.get('timestamp_utc', 'N/A'), "inline": False}
            ]
        }]
    }

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"✅ Notificación enviada a Discord ({reason}).")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar la alerta a Discord: {e}")


# --- FUNCIÓN DE RESILIENCIA (Cap. 5) ---

def send_to_ingest_api(data, max_retries=MAX_RETRIES):
    """Implementa la Resiliencia: Envía datos a la API con reintentos y backoff."""
    retries = 0
    while retries < max_retries:
        try:
            # Petición POST a la API de Alonso
            response = requests.post(API_INGEST_URL, json=data, timeout=5)
            response.raise_for_status()
            print(f"🟢 Éxito: Dato {data.get('id_paquete')} insertado correctamente.")
            return

        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"❌ Fallo de API/Red (Intento {retries}/{max_retries}): {e}")

            if retries < max_retries:
                # Retardo Exponencial (Backoff)
                wait_time = 2 ** retries
                print(f"⏳ Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                print(f"❌❌ FALLO CRÍTICO: Se agotaron los reintentos. Dato {data.get('id_paquete')} perdido.")
                return 


# --- LÓGICA DEL CEREBRO (Cap. 3 - Detección Múltiple) ---

def process_telemetry(data):
    """Aplica la lógica de estado y umbrales a cada dato."""
    global package_state
    
    # Adaptación a las claves del nuevo simulador
    temp = data.get('temperatura', 99.9)
    g_force = data.get('fuerza_g', 0.0) # Usando 'fuerza_g' del nuevo simulador
    puerta_abierta = data.get('puerta_abierta', False) # Nuevo sensor
    package_id = data.get('id_paquete', 'N/A')

    # Inicializar/Actualizar estado del paquete
    if package_id not in package_state:
        package_state[package_id] = {'consecutive': 0, 'is_alerting_temp': False, 'is_alerting_door': False}

    state = package_state[package_id]
    
    # ----------------------------------------------------
    # Detección 1: Alerta de Puerta Abierta (INMEDIATA)
    # ----------------------------------------------------
    if puerta_abierta:
        if not state['is_alerting_door']:
            # Enviar alerta solo la primera vez que se detecta el estado
            reason = "Puerta Abierta por Manipulación"
            print(f"🚨 PUERTA: {package_id} - {reason}. Enviando a Discord.")
            send_discord_alert(data, reason, DISCORD_WEBHOOK_DOOR)
            state['is_alerting_door'] = True # Bloqueamos para throttling
    else:
        # Resetear el throttling si la puerta se cierra
        if state['is_alerting_door']:
            print(f"🟢 PUERTA: {package_id} - Puerta cerrada. Reseteando alerta.")
        state['is_alerting_door'] = False
        
    # ----------------------------------------------------
    # Detección 2: Alerta de Temperatura/Impacto (SOSTENIDA)
    # ----------------------------------------------------
    is_temp_alert = temp > TEMP_UMBRAL
    is_g_force_alert = g_force > G_FORCE_UMBRAL # Detección de impacto
    is_alert_event_sostenido = is_temp_alert or is_g_force_alert
    
    reason_sostenida = ""
    if is_temp_alert and is_g_force_alert:
        reason_sostenida = "Temperatura y Posible Impacto"
    elif is_temp_alert:
        reason_sostenida = "Temperatura Excedida"
    elif is_g_force_alert:
        reason_sostenida = "Posible Impacto Sostenido"


    if is_alert_event_sostenido:
        state['consecutive'] += 1

        if state['consecutive'] >= CONSECUTIVE_EVENTS:
            # Solo enviar alerta a Discord si no se ha alertado ya (throttling)
            if not state['is_alerting_temp']:
                print(f"🚨 TEMP/G-FORCE: {package_id} - {reason_sostenida} SOSTENIDA. Enviando a Discord.")
                send_discord_alert(data, reason_sostenida, DISCORD_WEBHOOK_TEMP)
                state['is_alerting_temp'] = True # Bloqueamos futuras alertas
        
        else:
            print(f"🌡️ Advertencia: Pico temporal ({reason_sostenida}). Contador: {state['consecutive']}/{CONSECUTIVE_EVENTS}")

    else:
        # Dato bueno, reseteamos el contador y el estado de alerta
        if state['consecutive'] > 0:
            print(f"🟢 TEMP/G-FORCE: {package_id} - Volvió a la normalidad. Reseteando contador.")
        
        state['consecutive'] = 0
        state['is_alerting_temp'] = False # Permitimos que se dispare la alerta de nuevo


    # ⬇️ TAREA: Llamar a la función de envío resiliente para persistir el dato
    send_to_ingest_api(data)


# --- FUNCIONES MQTT y INICIO DEL SERVICIO ---

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
