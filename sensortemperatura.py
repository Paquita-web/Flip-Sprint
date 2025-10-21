"""
Simulador de sensor de temperatura (nacimiento del dato)
--------------------------------------------------------
Este script imita un sensor IoT que mide temperatura y publica
los datos en un broker MQTT (por defecto test.mosquitto.org).

Cada 2 segundos envía un mensaje JSON con:
- sensor_id: tipo de sensor (nevera_principal, nevera_puerta, sensor_carne)
- temperatura: valor simulado en °C
- unidad: siempre "C"
- timestamp: hora actual en formato ISO 8601 (UTC)

Ejemplo de ejecución:
    python sensor_temp_publisher.py --sensor-id nevera_principal
"""

import json
import time
import random
import argparse
from datetime import datetime, timezone
import paho.mqtt.client as mqtt


# --- Rangos de temperatura realistas por sensor ---
RANGOS = {
    "nevera_principal": (1.5, 4.5),
    "nevera_puerta": (2.0, 6.0),
    "sensor_carne": (0.5, 2.5),
}


# --- Función para obtener hora actual en formato ISO UTC ---
def ahora_iso_utc():
    return datetime.now(timezone.utc).isoformat()


# --- Función para simular temperatura con pequeñas variaciones ---
def sim_temp(tipo: str, base=None, variacion=0.3, prob_pico=0.03):
    """
    Genera una temperatura simulada según el tipo de sensor.
    """
    lo, hi = RANGOS.get(tipo, (2.0, 6.0))
    base = base if base is not None else (lo + hi) / 2
    t = base + random.uniform(-variacion, variacion)
    # A veces genera un pico anómalo (como si se abriera la puerta)
    if random.random() < prob_pico:
        t += random.uniform(1.5, 4.5)
    # Limitar dentro de un rango razonable
    return round(min(max(t, lo - 1.0), hi + 3.0), 2)


# --- Función principal ---
def main():
    ap = argparse.ArgumentParser(description="Sensor de temperatura → MQTT")
    ap.add_argument("--broker", default="test.mosquitto.org", help="Servidor MQTT (por defecto: test.mosquitto.org)")
    ap.add_argument("--port", type=int, default=1883, help="Puerto MQTT (por defecto: 1883)")
    ap.add_argument("--sensor-id", default="nevera_principal",
                    help="Tipo de sensor: nevera_principal | nevera_puerta | sensor_carne")
    ap.add_argument("--topic-root", default="greendelivery/sensors/temperature",
                    help="Ruta base del topic MQTT (por defecto: greendelivery/sensors/temperature)")
    ap.add_argument("--interval", type=float, default=2.0, help="Intervalo entre lecturas en segundos (por defecto: 2)")
    ap.add_argument("--qos", type=int, default=0, choices=[0, 1], help="Calidad de servicio MQTT (0 o 1)")
    args = ap.parse_args()

    # Construir el topic completo (ej: greendelivery/sensors/temperature/nevera_principal)
    topic = f"{args.topic_root}/{args.sensor_id}"

    # Crear el cliente MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sensor-{args.sensor_id}")
    print(f"[INFO] Conectando al broker MQTT {args.broker}:{args.port} ...")
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    print(f"[INFO] Publicando datos en el tópico: {topic}")
    print("[INFO] Presiona Ctrl + C para detener el sensor.\n")

    try:
        while True:
            temp = sim_temp(args.sensor_id)
            payload = {
                "sensor_id": args.sensor_id,
                "temperatura": temp,
                "unidad": "C",
                "timestamp": ahora_iso_utc()
            }
            msg = json.dumps(payload, ensure_ascii=False)
            r = client.publish(topic, msg, qos=args.qos)
            if r.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[ERROR] No se pudo publicar (rc={r.rc})")
            else:
                print(f"[PUBLISH] {topic} → {msg}")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[SALIDA] Sensor detenido manualmente.")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[INFO] Desconectado del broker MQTT.")


# --- Punto de entrada ---
if __name__ == "__main__":
    main()
