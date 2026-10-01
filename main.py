import os
import secrets
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

# Umgebungsvariablen aus .env Datei laden
load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
PI_TOKEN = os.getenv("PI_TOKEN")

if not APP_TOKEN or not PI_TOKEN:
    raise RuntimeError("FEHLER: APP_TOKEN oder PI_TOKEN wurden nicht in den Environment-Variablen gefunden!")

app = FastAPI(
    title="Raspi-Linker Broker",
    description="Sicherer Vermittler zwischen Android-App und Raspberry Pi",
    version="1.0.0"
)

security = HTTPBearer()


# ------------------------------------------------------------------
# WebSocket Connection Manager (Verwaltet die Verbindung zum Pi)
# ------------------------------------------------------------------
class PiConnectionManager:
    def __init__(self):
        # Hält die aktive WebSocket-Verbindung zum Pi im RAM
        self.active_connection: Optional[WebSocket] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection = websocket

    def disconnect(self):
        self.active_connection = None

    @property
    def is_connected(self) -> bool:
        return self.active_connection is not None

    async def send_command(self, command: dict) -> bool:
        """Sendet einen JSON-Befehl an den verbundenen Pi."""
        if self.active_connection:
            await self.active_connection.send_json(command)
            return True
        return False


manager = PiConnectionManager()


# ------------------------------------------------------------------
# Sicherheits-Hilfsfunktionen
# ------------------------------------------------------------------
def verify_app_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Prüft den Bearer-Token der Android-App zeit-sicher."""
    if not secrets.compare_digest(credentials.credentials, APP_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger APP_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ------------------------------------------------------------------
# Datenmodell für Befehle von der App
# ------------------------------------------------------------------
class CommandRequest(BaseModel):
    action: str
    payload: Optional[dict] = None


# ------------------------------------------------------------------
# Endpunkte
# ------------------------------------------------------------------

@app.get("/")
async def root():
    """Öffentlicher Health-Check Endpunkt."""
    return {
        "status": "online",
        "pi_connected": manager.is_connected
    }


@app.websocket("/ws/pi")
async def websocket_pi_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket-Endpunkt für den Raspberry Pi.
    Aufruf: wss://dein-server.onrender.com/ws/pi?token=DEIN_PI_TOKEN
    """
    # 1. Token des Pi vor der Akzeptanz prüfen
    if not token or not secrets.compare_digest(token, PI_TOKEN):
        # Verbindung ablehnen mit Code 4001 (Unauthorized)
        await websocket.close(code=4001, reason="Ungültiger PI_TOKEN")
        return

    # 2. Verbindung annehmen & im Manager registrieren
    await manager.connect(websocket)
    print("🟢 Raspberry Pi hat sich erfolgreich verbunden!")

    try:
        while True:
            # Auf Nachrichten/Heartbeats vom Pi warten
            data = await websocket.receive_text()
            print(f"Empfangen vom Pi: {data}")
            # Hier könnten Status-Updates vom Pi verarbeitet werden (z.B. Temperatur)

    except WebSocketDisconnect:
        manager.disconnect()
        print("🔴 Raspberry Pi hat die Verbindung getrennt.")


@app.post("/api/command")
async def send_command_to_pi(
    cmd: CommandRequest, 
    _: str = Depends(verify_app_token)
):
    """
    HTTP-POST Endpunkt für die Android App.
    Erfordert den APP_TOKEN im Authorization-Header (Bearer Token).
    """
    # 1. Prüfen, ob der Pi überhaupt online ist
    if not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raspberry Pi ist aktuell nicht mit dem Server verbunden."
        )

    # 2. Befehl an den Pi über die offene WebSocket-Verbindung leiten
    success = await manager.send_command(cmd.model_dump())
    if success:
        return {"status": "success", "message": f"Befehl '{cmd.action}' an Pi gesendet."}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Senden des Befehls an den Pi."
        )
