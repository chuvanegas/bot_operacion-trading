"""
Configuración central del bot de trading IQ Option PCRV4.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Credenciales IQ Option ────────────────────────────────────────────────────
IQOPTION_EMAIL    = os.getenv("IQOPTION_EMAIL", "")
IQOPTION_PASSWORD = os.getenv("IQOPTION_PASSWORD", "")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Activo y tipo de opción ───────────────────────────────────────────────────
ASSET          = os.getenv("ASSET", "XAUUSD")          # Gold
OPTION_TYPE    = os.getenv("OPTION_TYPE", "turbo")     # turbo | digital | binary
EXPIRY_SECONDS = int(os.getenv("EXPIRY_SECONDS", "60"))

# ── Money management ──────────────────────────────────────────────────────────
BASE_AMOUNT        = float(os.getenv("BASE_AMOUNT", "1.0"))
MONEY_MANAGEMENT   = os.getenv("MONEY_MANAGEMENT", "FIXED")   # FIXED | MARTINGALE | ANTI_MARTINGALE
MARTINGALE_FACTOR  = float(os.getenv("MARTINGALE_FACTOR", "2.0"))

# ── Límites de riesgo diario ──────────────────────────────────────────────────
DAILY_STOP_LOSS_PCT   = float(os.getenv("DAILY_STOP_LOSS_PCT", "10.0"))   # % pérdida máxima
DAILY_TAKE_PROFIT_PCT = float(os.getenv("DAILY_TAKE_PROFIT_PCT", "20.0")) # % ganancia máxima

# ── Señal ─────────────────────────────────────────────────────────────────────
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.55"))

# ── Pago de IQ Option ─────────────────────────────────────────────────────────
PAYOUT_RATE = float(os.getenv("PAYOUT_RATE", "0.80"))  # 80% payout típico

# ── Modo demo / real ──────────────────────────────────────────────────────────
USE_DEMO = os.getenv("USE_DEMO", "true").lower() == "true"
