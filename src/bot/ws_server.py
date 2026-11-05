"""
Servidor WebSocket local — conecta el bot con la app web del navegador.

El bot empuja estado cada segundo.
El navegador envía 'approve' o 'cancel' cuando el usuario decide.
"""
import json
import asyncio
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    logger.warning("websockets no instalado — app web deshabilitada. Instala: pip install websockets")

HOST = "localhost"
PORT = 8765

# Estado compartido entre bot y servidor
_state: dict = {
    "connected":    False,
    "account_type": "PRACTICE",
    "balance":      0.0,
    "balance_start": 0.0,
    "asset":        "XAUUSD",
    "price":        0.0,
    "signal":       None,
    "confidence":   0.0,
    "score":        0.0,
    "pcrv4":        {"active": False, "reason": "Sin datos"},
    "gates":        [],
    "verdict":      "—",
    "block_reason": None,
    "trend":        {"short": "—", "long": "—", "adx": 0},
    "layers":       {},
    "reasons":      [],
    "daily":        {"pnl": 0.0, "wins": 0, "trades": 0, "win_rate": 0},
    "history":      [],
    "pending_approval": False,
    "last_update":  "",
    "bot_status":   "INICIANDO",
}

# Cola de respuestas de aprobación
_approval_queue: asyncio.Queue | None = None
_clients: set = set()
_loop: asyncio.AbstractEventLoop | None = None


def update_state(**kwargs):
    """Llama desde el bot para actualizar el estado."""
    _state.update(kwargs)
    _state["last_update"] = datetime.now().strftime("%H:%M:%S")
    _broadcast_sync()


def _broadcast_sync():
    """Envía el estado a todos los clientes (thread-safe)."""
    if _loop and _loop.is_running() and _clients:
        asyncio.run_coroutine_threadsafe(_broadcast(), _loop)


async def _broadcast():
    if not _clients:
        return
    msg = json.dumps(_state, default=str)
    dead = set()
    for ws in _clients:
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


async def _handler(websocket):
    global _approval_queue
    _clients.add(websocket)
    logger.info(f"Navegador conectado ({len(_clients)} total)")
    # Enviar estado actual inmediatamente
    await websocket.send(json.dumps(_state, default=str))
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")
                if action in ("approve", "cancel") and _approval_queue:
                    await _approval_queue.put(action)
                    logger.info(f"Acción recibida del navegador: {action}")
            except Exception as e:
                logger.warning(f"Mensaje inválido del navegador: {e}")
    except Exception:
        pass
    finally:
        _clients.discard(websocket)
        logger.info("Navegador desconectado")


async def _run_server():
    global _loop, _approval_queue
    _loop = asyncio.get_running_loop()
    _approval_queue = asyncio.Queue()
    async with websockets.serve(_handler, HOST, PORT):
        logger.info(f"App web disponible en: http://localhost:{PORT} (WebSocket ws://localhost:{PORT})")
        await asyncio.Future()  # corre para siempre


def start_server():
    """Inicia el servidor en un hilo separado."""
    if not WS_AVAILABLE:
        return
    t = threading.Thread(target=lambda: asyncio.run(_run_server()), daemon=True)
    t.start()


async def wait_for_approval(timeout: int = 50) -> bool:
    """
    Espera aprobación del navegador. Devuelve True=aprobado, False=cancelado/timeout.
    Debe llamarse desde un contexto async.
    """
    if _approval_queue is None:
        return False
    # Limpiar cola anterior
    while not _approval_queue.empty():
        try:
            _approval_queue.get_nowait()
        except Exception:
            break
    try:
        result = await asyncio.wait_for(_approval_queue.get(), timeout=timeout)
        return result == "approve"
    except asyncio.TimeoutError:
        return False


def has_web_client() -> bool:
    return len(_clients) > 0
