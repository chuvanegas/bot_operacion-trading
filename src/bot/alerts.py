"""
Alertas — inspirado en trader-alerts, adaptado para señales PCRV4 en IQ Option.
Cada alerta se dispara UNA SOLA VEZ (no spam) y puede reenviarse por Telegram.
"""
import time
import logging
import requests
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

_fired: set = set()


def _telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
                                 "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        logger.warning(f"Telegram error: {e}")


def alert_signal(signal: str, asset: str, confidence: float, reasons: list,
                 pcrv4_active: bool, price: float):
    key = f"signal_{signal}_{int(time.time() // 60)}"
    if key in _fired:
        return
    _fired.add(key)

    icon = "🟢" if signal == "call" else "🔴"
    pcrv4_tag = " 🎯PCRV4" if pcrv4_active else ""
    msg = (f"{icon} *{signal.upper()}* {asset}{pcrv4_tag}\n"
           f"Precio: `{price:.5f}` | Conf: `{confidence:.1%}`\n"
           f"Razones: {', '.join(reasons[:3])}")
    _telegram(msg)
    logger.info(f"ALERTA enviada: {signal.upper()} {asset} conf={confidence:.1%}")


def alert_result(signal: str, asset: str, outcome: str, profit: float, balance: float):
    key = f"result_{outcome}_{int(time.time() // 60)}"
    if key in _fired:
        return
    _fired.add(key)

    icon = "✅" if outcome == "win" else "❌"
    msg = (f"{icon} *{outcome.upper()}* {signal.upper()} {asset}\n"
           f"P&L: `{profit:+.2f}` | Balance: `{balance:.2f}`")
    _telegram(msg)


def alert_daily_limit(limit_type: str, balance: float, day_start: float):
    key = f"limit_{limit_type}"
    if key in _fired:
        return
    _fired.add(key)

    pct = abs(balance - day_start) / day_start * 100
    icon = "🛑" if limit_type == "stop_loss" else "🎉"
    msg = (f"{icon} *{limit_type.upper().replace('_', ' ')}* alcanzado\n"
           f"Balance: `{balance:.2f}` | Variación: `{pct:.1f}%`")
    _telegram(msg)


def reset_daily():
    _fired.clear()
