#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simulador de paquete con múltiples sensores (camión Galicia → Madrid)
Publica un JSON por lectura con:
- id_paquete
- timestamp_utc
- temperatura (lógica del script original + efecto puerta abierta)
- fuerza_g
- puerta_abierta (episodios de minutos)
- latitud, longitud (ruta simulada Galicia → Madrid)
"""

import json
import time
import random
import argparse
from datetime import datetime, timezone, timedelta
import paho.mqtt.client as mqtt

# ---------------------------
# Configuración de la simulación
# ---------------------------

# Ruta aproximada: Santiago de Compostela → Ourense → Zamora → Valladolid → Segovia → Madrid
WAYPOINTS = [
    (42.8806, -8.5456),  # Santiago de Compostela (Galicia)
    (42.3360, -7.8640),  # Ourense
    (41.5033, -5.7440),  # Zamora
    (41.6523, -4.7245),  # Valladolid
    (40.9429, -4.1088),  # Segovia
    (40.4167, -3.7038),  # Madrid
]

# --- Temperatura (estilo script original) ---
# Rango realista de cámara refrigerada similar a "nevera_principal"
RANGO_TEMP = (1.5, 4.5)      # lo, hi
TEMP_VARIACION = 0.3         # pequeñas variaciones
TEMP_PROB_PICO = 0.03        # picos anómalos ocasionales
TEMP_MAX_DELTA_OPEN = 0.6    # aumento adicional mientras puerta está abierta (ligero)

# Fuerza G típica en camión
G_BASE = 1.0
G_JITTER = 0.05
G_BUMP_PROB = 0.02
G_BUMP_MAG = (0.1, 0.35)

# Puerta abierta en episodios de minutos, poco frecuente
DOOR_EPISODE_START_PROB_PER_MIN = 0.03
DOOR_EPISODE_DURATION_S = (60, 300)

# Avance por tick en la ruta (interpolación lineal)
ROUTE_PROGRESS_PER_TICK = 0.015

def ahora_iso_utc():
    return datetime.now(timezone.utc).isoformat()

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

class DoorEpisode:
    def __init__(self):
        self.open_until = None

    def maybe_start(self, now, interval_s):
        if self.is_open(now):
            return
        p_tick = DOOR_EPISODE_START_PROB_PER_MIN * (interval_s / 60.0)
        if random.random() < p_tick:
            dur = random.uniform(*DOOR_EPISODE_DURATION_S)
            self.open_until = now + timedelta(seconds=dur)

    def is_open(self, now):
        return self.open_until is not None and now < self.open_until

    def ensure_reset(self, now):
        if self.open_until is not None and now >= self.open_until:
            self.open_until = None

class RouteCursor:
    def __init__(self, waypoints, loop=False):
        self.wps = waypoints
        self.loop = loop
        self.seg_idx = 0
        self.t = 0.0

    def step(self, step_t):
        if self.seg_idx >= len(self.wps) - 1:
            return self.wps[-1]
        self.t += step_t
        while self.t >= 1.0:
            self.t -= 1.0
            self.seg_idx += 1
            if self.seg_idx >= len(self.wps) - 1:
                if self.loop:
                    self.seg_idx = 0
                else:
                    return self.wps[-1]
        (lat0, lon0) = self.wps[self.seg_idx]
        (lat1, lon1) = self.wps[self.seg_idx + 1]
        lat = lat0 + (lat1 - lat0) * self.t
        lon = lon0 + (lon1 - lon0) * self.t
        lat += random.uniform(-0.0005, 0.0005)  # pequeño serpenteo
        lon += random.uniform(-0.0005, 0.0005)
        return (lat, lon)

def sim_fuerza_g():
    g = G_BASE + random.uniform(-G_JITTER, G_JITTER)
    if random.random() < G_BUMP_PROB:
        g += random.uniform(*G_BUMP_MAG)
    return round(clamp(g, 0.6, 1.6), 3)

# === NUEVO: temperatura igual que el script original, + efecto puerta abierta ===
def sim_temperatura_like_original(puerta_abierta: bool, base=None, variacion=TEMP_VARIACION, prob_pico=TEMP_PROB_PICO):
    lo, hi = RANGO_TEMP
    base = base if base is not None else (lo + hi) / 2
    t = base + random.uniform(-variacion, variacion)
    # Pico anómalo ocasional (como el original)
    if random.random() < prob_pico:
        t += random.uniform(1.5, 4.5)
    # Efecto adicional si la puerta está abierta (sube un poco)
    if puerta_abierta:
        t += random.uniform(0.0, TEMP_MAX_DELTA_OPEN)
    # Limitar a rango razonable y redondear
    return round(clamp(t, lo - 1.0, hi + 3.0), 2)

def build_payload(id_paquete, lat, lon, puerta_abierta):
    return {
        "id_paquete": id_paquete,
        "timestamp_utc": ahora_iso_utc(),
        "temperatura": sim_temperatura_like_original(puerta_abierta),
        "fuerza_g": sim_fuerza_g(),
        "puerta_abierta": puerta_abierta,
        "latitud": round(lat, 6),
        "longitud": round(lon, 6),
    }

def main():
    ap = argparse.ArgumentParser(description="Simulador de paquete (multi-sensor) → MQTT")
    ap.add_argument("--broker", default="test.mosquitto.org", help="Servidor MQTT (por defecto: test.mosquitto.org)")
    ap.add_argument("--port", type=int, default=1883, help="Puerto MQTT (por defecto: 1883)")
    ap.add_argument("--id-paquete", default="PKG-A123", help="Identificador del paquete (constante)")
    ap.add_argument("--topic-root", default="greendelivery/packages",
                    help="Ruta base del topic MQTT (por defecto: greendelivery/packages)")
    ap.add_argument("--interval", type=float, default=2.0, help="Intervalo entre lecturas en segundos (por defecto: 2)")
    ap.add_argument("--qos", type=int, default=0, choices=[0, 1], help="Calidad de servicio MQTT (0 o 1)")
    ap.add_argument("--loop-route", action="store_true", help="Al llegar a Madrid vuelve a empezar la ruta")
    args = ap.parse_args()

    topic = f"{args.topic_root}/{args.id_paquete}"

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pkg-{args.id_paquete}")
    print(f"[INFO] Conectando a {args.broker}:{args.port} ...")
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    print(f"[INFO] Publicando en: {topic}")
    print("[INFO] Ctrl+C para detener.\n")

    door = DoorEpisode()
    route = RouteCursor(WAYPOINTS, loop=args.loop_route)

    try:
        while True:
            now = datetime.now(timezone.utc)
            door.ensure_reset(now)
            door.maybe_start(now, args.interval)
            puerta_abierta = door.is_open(now)

            lat, lon = route.step(ROUTE_PROGRESS_PER_TICK)

            payload = build_payload(args.id_paquete, lat, lon, puerta_abierta)
            msg = json.dumps(payload, ensure_ascii=False)

            r = client.publish(topic, msg, qos=args.qos)
            if r.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[ERROR] No se pudo publicar (rc={r.rc})")
            else:
                print(f"[PUBLISH] {topic} → {msg}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[SALIDA] Simulación detenida.")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[INFO] Desconectado del broker MQTT.")

if __name__ == "__main__":
    main()
