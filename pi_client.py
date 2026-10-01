import os
import time
import json
import websocket
from dotenv import load_dotenv

# .env Datei auf dem Raspi laden
load_dotenv()

# WebSocket-URL deines Render-Servers (z. B. wss://dein-broker.onrender.com)
# Für lokale Tests nutzen wir ws://localhost:8000
SERVER_URL = os.getenv("SERVER_URL", "ws://localhost:8000")
PI_TOKEN = os.getenv("PI_TOKEN")

if not PI_TOKEN:
    raise RuntimeError("FEHLER: PI_TOKEN wurde nicht in der .env-Datei gefunden!")


def on_message(ws, message):
    """Wird aufgerufen, wenn die Android-App einen Befehl über den Server schickt."""
    print(f"\n📩 Befehl empfangen: {message}")
    
    try:
        data = json.loads(message)
        action = data.get("action")
        payload = data.get("payload", {})
        
        # Hier führst du deine Raspi-Aktionen aus
        handle_command(action, payload)
        
    except json.JSONDecodeError:
        print("⚠️ Ungültiges JSON-Format empfangen.")


def handle_command(action: str, payload: dict):
    """Hier steuerst du deine Hardware / Logik auf dem Pi."""
    if action == "status":
        print("📊 Statusabfrage erhalten.")
        
    elif action == "toggle_gpio":
        pin = payload.get("pin")
        print(f"🔌 Schalte GPIO-Pin {pin}...")
        # Hier später z.B. RPi.GPIO nutzen
        
    elif action == "reboot":
        print("🔄 System-Neustart angefordert (Demo)...")
        
    else:
        print(f"❓ Unbekannter Befehl: '{action}'")


def on_error(ws, error):
    """Fehlerbehandlung für den WebSocket."""
    print(f"❌ WebSocket-Fehler: {error}")


def on_close(ws, close_status_code, close_msg):
    """Wird aufgerufen, wenn die Verbindung (z. B. durch Server-Neustart) trennt."""
    print(f"🔴 Verbindung getrennt ({close_status_code}: {close_msg})")


def on_open(ws):
    """Wird aufgerufen, sobald der Pi erfolgreich verbunden ist."""
    print("🟢 Erfolgreich mit dem Render-Server verbunden! Warte auf Befehle...")


def run_client():
    # WebSocket-URL mit Token als Query-Parameter zusammensetzen
    # Bei Render muss es wss:// sein, lokal ws://
    protocol = "wss" if SERVER_URL.startswith("https") or SERVER_URL.startswith("wss") else "ws"
    base_url = SERVER_URL.replace("https://", "").replace("http://", "").replace("wss://", "").replace("ws://", "")
    
    ws_url = f"{protocol}://{base_url}/ws/pi?token={PI_TOKEN}"

    while True:
        print(f"🔄 Verbinde mit {ws_url} ...")
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # ping_interval=30 schickt alle 30s ein Ping-Paket an Render, 
            # damit Render die Verbindung nicht wegen Inaktivität schließt.
            ws.run_forever(ping_interval=30, ping_timeout=10)
            
        except Exception as e:
            print(f"⚠️ Unerwartetes Problem: {e}")

        # Wenn der Server neustartet oder die Verbindung abbricht:
        print("⏳ Verbindung verloren. Erneuter Versuch in 5 Sekunden...")
        time.sleep(5)


if __name__ == "__main__":
    run_client()
