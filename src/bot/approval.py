"""
Aprobación manual via Telegram inline keyboard.

Flujo:
  1. Bot detecta señal válida (todos los gates PASS)
  2. Envía mensaje con botones ✅ APROBAR / ❌ CANCELAR
  3. Espera respuesta hasta TIMEOUT segundos
  4. Devuelve True si aprobado, False si cancelado/timeout
"""
import time
import logging
import requests
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TIMEOUT = 50        # segundos máximos para responder (antes del vencimiento de 1m)
POLL_INTERVAL = 1   # cada cuánto revisar respuesta

_last_update_id: int = 0


def _api(method: str, **kwargs) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=kwargs, timeout=5)
        return r.json()
    except Exception as e:
        logger.warning(f"Telegram API error ({method}): {e}")
        return {}


def _send_approval_message(signal: str, asset: str, price: float,
                            confidence: float, score: float,
                            pcrv4_active: bool, reasons: list) -> int | None:
    """Envía mensaje con botones inline y devuelve message_id."""
    icon   = "🟢" if signal == "call" else "🔴"
    pcrv4s = "🎯 PCRV4 ACTIVO" if pcrv4_active else "⬜ sin patrón PCRV4"
    text = (
        f"{icon} *SEÑAL DETECTADA — APROBACIÓN REQUERIDA*\n\n"
        f"📌 Activo  : `{asset}`\n"
        f"📈 Señal   : *{signal.upper()}*\n"
        f"💵 Precio  : `{price:.5f}`\n"
        f"🎯 Conf    : `{confidence:.1%}`\n"
        f"📊 Score   : `{score:.2f}`\n"
        f"🕯 {pcrv4s}\n\n"
        f"📋 Razones: _{', '.join(reasons[:4])}_\n\n"
        f"⏰ *Tienes {TIMEOUT}s para responder*"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ APROBAR",   "callback_data": "approve"},
            {"text": "❌ CANCELAR",  "callback_data": "cancel"},
        ]]
    }
    resp = _api(
        "sendMessage",
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    if resp.get("ok"):
        return resp["result"]["message_id"]
    return None


def _edit_message(message_id: int, result: str):
    """Actualiza el mensaje con el resultado final."""
    text = "✅ *APROBADO — operación ejecutada*" if result == "approved" \
           else "❌ *CANCELADO por el usuario*" if result == "cancelled" \
           else "⏱ *TIEMPO AGOTADO — señal descartada*"
    _api("editMessageText",
         chat_id=TELEGRAM_CHAT_ID,
         message_id=message_id,
         text=text,
         parse_mode="Markdown")


def _poll_approval(timeout: int) -> bool | None:
    """
    Sondea getUpdates buscando un callback_data de aprobación o cancelación.
    Devuelve True (aprobado), False (cancelado), None (timeout).
    """
    global _last_update_id
    deadline = time.time() + timeout

    while time.time() < deadline:
        resp = _api("getUpdates", offset=_last_update_id + 1, timeout=POLL_INTERVAL)
        updates = resp.get("result", [])

        for upd in updates:
            _last_update_id = upd["update_id"]
            cb = upd.get("callback_query")
            if cb:
                # Responder al callback para quitar el ícono de carga
                _api("answerCallbackQuery", callback_query_id=cb["id"])
                data = cb.get("data", "")
                if data == "approve":
                    return True
                if data == "cancel":
                    return False

        time.sleep(POLL_INTERVAL)

    return None   # timeout


def request_approval(signal: str, asset: str, price: float,
                     confidence: float, score: float,
                     pcrv4_active: bool, reasons: list) -> bool:
    """
    Solicita aprobación al usuario vía Telegram.
    Devuelve True si aprobó, False en cualquier otro caso.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram no configurado — operación bloqueada (modo manual)")
        return False

    logger.info(f"Solicitando aprobación: {signal.upper()} {asset} conf={confidence:.1%}")
    msg_id = _send_approval_message(signal, asset, price, confidence,
                                    score, pcrv4_active, reasons)
    if msg_id is None:
        logger.error("No se pudo enviar mensaje de aprobación")
        return False

    result = _poll_approval(TIMEOUT)

    if result is True:
        _edit_message(msg_id, "approved")
        logger.info("✅ Operación APROBADA por usuario")
        return True
    elif result is False:
        _edit_message(msg_id, "cancelled")
        logger.info("❌ Operación CANCELADA por usuario")
        return False
    else:
        _edit_message(msg_id, "timeout")
        logger.warning("⏱ Tiempo agotado — señal descartada")
        return False
