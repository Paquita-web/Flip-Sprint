#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Alertas MQTT → Discord (auto)
- Temperatura > 7.0 °C → canal #sensor-temperatura
- Puerta abierta → canal #sensor-puerta
- Antiflood (cooldown) y (opcional) mensaje de recuperación

Ejecuta:
    python alertas_discord_auto.py
"""

import json, time, os
from datetime import datetime, timezone
import requests
import paho.mqtt.client as mqtt

# =======================
# CONFIG (EDITA SOLO ESTO)
# =======================
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC = "greendelivery/packages/PKG-A123"   # escucha todos los paquetes

# Webhooks de Discord (pon los tuyos)
WEBHOOK_TEMP = "https://discord.com/api/webhooks/1435914370914844773/CYJB_csvH-RJDwIIaKWFLou2S85CI91Fw-XX3J30vNeM9dMURka0zFh_DgTt4wlzO68Q"
WEBHOOK_DOOR = "https://discord.com/api/webhooks/1435914160985870436/XgDa7PsvQJc5asJFpsWA8MfujYLfaiCW3u-XjJRs7g-ZZ_Qjf5vEkGs3mVs8mOQrz3Ce"

# Umbrales y comportamiento
TEMP_THRESHOLD = 6.0          # °C (solo alertar si > 7.0)
RECOVERY_DELTA = 0.5          # histeresis para recuperación (7.0 - 0.5 = 6.5)
SEND_RECOVERY = False         # cambia a True si quieres mensaje de recuperación
COOLDOWN_SECONDS = 60        # no repetir misma alerta del mismo paquete antes de 3 min

# =======================

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _gmaps(lat, lon):
    if lat is None or lon is None: return ""
    return f"https://maps.google.com/?q={lat},{lon}"

def _post_discord(hook, content):
    try:
        r = requests.post(hook, json={"content": content}, timeout=10)
        if r.status_code >= 300:
            print(f"[WARN] Discord {r.status_code}: {r.text[:200]}")
        else:
            print(f"[DISCORD] {content}")
    except Exception as e:
        print(f"[ERROR] Discord: {e}")

class State:
    def __init__(self):
        self.temp_high = {}          # pkg_id -> bool
        self.door_open = {}          # pkg_id -> bool
        self.last_sent = {}          # (pkg_id, kind) -> ts

    def can_send(self, pkg_id, kind):
        now = time.time()
        key = (pkg_id, kind)
        last = self.last_sent.get(key, 0)
        if now - last >= COOLDOWN_SECONDS:
            self.last_sent[key] = now
            return True
        return False

def main():
    # Validación mínima
    if not (WEBHOOK_TEMP.startswith("https://discord.com/api/webhooks/1435914370914844773/CYJB_csvH-RJDwIIaKWFLou2S85CI91Fw-XX3J30vNeM9dMURka0zFh_DgTt4wlzO68Q") and
            WEBHOOK_DOOR.startswith("https://discord.com/api/webhooks/1435914160985870436/XgDa7PsvQJc5asJFpsWA8MfujYLfaiCW3u-XjJRs7g-ZZ_Qjf5vEkGs3mVs8mOQrz3Ce")):
        print("❌ Pon tus URLs de webhook en el bloque CONFIG (WEBHOOK_TEMP / WEBHOOK_DOOR).")
        return

    st = State()

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception as e:
            print(f"[WARN] JSON inválido en {msg.topic}: {e}")
            return

        pkg = data.get("id_paquete") or "DESCONOCIDO"
        temp = data.get("temperatura")
        door = data.get("puerta_abierta")
        lat, lon = data.get("latitud"), data.get("longitud")
        ts = data.get("timestamp_utc") or _now_iso()

        # --- Temperatura ---
        if isinstance(temp, (int, float)):
            high = temp > TEMP_THRESHOLD
            prev = st.temp_high.get(pkg, False)

            if high and not prev and st.can_send(pkg, "temp"):
                link = _gmaps(lat, lon)
                _post_discord(
                    WEBHOOK_TEMP,
                    f"⚠️ **Temperatura alta** en `{pkg}`: **{temp:.2f} °C** (> {TEMP_THRESHOLD:.1f})\n"
                    f"📍 {lat},{lon} {('(mapa: ' + link + ')') if link else ''}\n"
                    f"🕒 {ts}"
                )
                st.temp_high[pkg] = True

            if SEND_RECOVERY and prev and (not high) and temp <= (TEMP_THRESHOLD - RECOVERY_DELTA) and st.can_send(pkg, "temp"):
                link = _gmaps(lat, lon)
                _post_discord(
                    WEBHOOK_TEMP,
                    f"✅ **Temperatura recuperada** en `{pkg}`: **{temp:.2f} °C** (≤ {TEMP_THRESHOLD-RECOVERY_DELTA:.1f})\n"
                    f"📍 {lat},{lon} {('(mapa: ' + link + ')') if link else ''}\n"
                    f"🕒 {ts}"
                )
                st.temp_high[pkg] = False

        # --- Puerta ---
        if isinstance(door, bool):
            was_open = st.door_open.get(pkg, False)

            if door and not was_open and st.can_send(pkg, "door"):
                link = _gmaps(lat, lon)
                _post_discord(
                    WEBHOOK_DOOR,
                    f"🚪 **Puerta ABIERTA** en `{pkg}`\n"
                    f"📍 {lat},{lon} {('(mapa: ' + link + ')') if link else ''}\n"
                    f"🕒 {ts}"
                )
                st.door_open[pkg] = True

            if SEND_RECOVERY and (not door) and was_open and st.can_send(pkg, "door"):
                link = _gmaps(lat, lon)
                _post_discord(
                    WEBHOOK_DOOR,
                    f"🔒 **Puerta CERRADA** en `{pkg}`\n"
                    f"📍 {lat},{lon} {('(mapa: ' + link + ')') if link else ''}\n"
                    f"🕒 {ts}"
                )
                st.door_open[pkg] = False

    print(f"[INFO] Suscribiendo {TOPIC} en {BROKER}:{PORT} …")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="discord-alerts-auto")
    client.on_message = on_message
    client.connect(BROKER, PORT, 30)
    client.subscribe(TOPIC, qos=0)
    client.loop_forever()

if __name__ == "__main__":
    main()
