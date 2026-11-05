"""
Cliente IQ Option con reconexión automática y soporte para digital/turbo/binary.
"""
import time
import logging
import pandas as pd
from iqoptionapi.stable_api import IQ_Option
from config.settings import IQOPTION_EMAIL, IQOPTION_PASSWORD, USE_DEMO

logger = logging.getLogger(__name__)

ACCOUNT_TYPE = "PRACTICE" if USE_DEMO else "REAL"
MAX_RETRIES  = 5


class IQOptionClient:
    def __init__(self):
        self.api   = IQ_Option(IQOPTION_EMAIL, IQOPTION_PASSWORD)
        self._connected = False

    # ── Conexión ──────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                status, reason = self.api.connect()
                if status:
                    self.api.change_balance(ACCOUNT_TYPE)
                    self._connected = True
                    logger.info(f"IQ Option conectado [{ACCOUNT_TYPE}]")
                    return True
                logger.warning(f"Intento {attempt}/{MAX_RETRIES}: {reason}")
            except Exception as e:
                logger.warning(f"Intento {attempt}/{MAX_RETRIES}: {e}")
            time.sleep(2 ** attempt)
        return False

    def ensure_connected(self):
        if not self.api.check_connect():
            logger.warning("Desconectado — reconectando…")
            self.connect()

    # ── Datos de mercado ──────────────────────────────────────────────────────
    def get_candles(self, asset: str, interval: int, count: int) -> pd.DataFrame:
        self.ensure_connected()
        candles = self.api.get_candles(asset, interval, count, time.time())
        df = pd.DataFrame(candles)
        df["open"]  = df["open"].astype(float)
        df["close"] = df["close"].astype(float)
        df["high"]  = df["max"].astype(float)
        df["low"]   = df["min"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.sort_values("from", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df[["from", "open", "high", "low", "close", "volume"]]

    def get_balance(self) -> float:
        self.ensure_connected()
        return float(self.api.get_balance())

    def is_asset_open(self, asset: str, option_type: str) -> bool:
        self.ensure_connected()
        try:
            return self.api.get_all_open_time()[option_type][asset]["open"]
        except Exception:
            return False

    # ── Operaciones ───────────────────────────────────────────────────────────
    def buy(self, asset: str, amount: float, direction: str, expiry: int,
            option_type: str) -> tuple[bool, int]:
        self.ensure_connected()
        try:
            if option_type == "digital":
                status, order_id = self.api.buy_digital_spot(asset, amount, direction, expiry)
            else:
                status, order_id = self.api.buy(amount, asset, direction, expiry)
            return status, order_id
        except Exception as e:
            logger.error(f"Error buy: {e}")
            return False, -1

    def check_win(self, order_id: int, option_type: str) -> tuple[str, float]:
        self.ensure_connected()
        try:
            if option_type == "digital":
                status, profit = self.api.check_win_digital_v2(order_id)
            else:
                profit = self.api.check_win_v3(order_id)
                status = profit > 0
            outcome = "win" if profit > 0 else "lose"
            return outcome, float(profit)
        except Exception as e:
            logger.error(f"Error check_win: {e}")
            return "error", 0.0
