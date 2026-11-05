"""
Gestión de dinero: FIXED, MARTINGALE, ANTI_MARTINGALE.
"""
import logging
from config.settings import (BASE_AMOUNT, MONEY_MANAGEMENT, MARTINGALE_FACTOR,
                              DAILY_STOP_LOSS_PCT, DAILY_TAKE_PROFIT_PCT)

logger = logging.getLogger(__name__)


class MoneyManager:
    def __init__(self):
        self.reset_day(0.0)

    def reset_day(self, balance: float):
        self._day_start    = balance
        self._current_amt  = BASE_AMOUNT
        self._last_outcome = None
        self._daily_trades = 0
        self._daily_wins   = 0
        self._daily_pnl    = 0.0

    def get_amount(self) -> float:
        mm = MONEY_MANAGEMENT.upper()
        if mm == "MARTINGALE":
            if self._last_outcome == "lose":
                self._current_amt = min(self._current_amt * MARTINGALE_FACTOR,
                                        BASE_AMOUNT * 8)
            else:
                self._current_amt = BASE_AMOUNT
        elif mm == "ANTI_MARTINGALE":
            if self._last_outcome == "win":
                self._current_amt = min(self._current_amt * 1.5, BASE_AMOUNT * 4)
            else:
                self._current_amt = BASE_AMOUNT
        else:
            self._current_amt = BASE_AMOUNT
        return round(self._current_amt, 2)

    def register_result(self, outcome: str, profit: float):
        self._last_outcome  = outcome
        self._daily_trades += 1
        self._daily_pnl    += profit
        if outcome == "win":
            self._daily_wins += 1
        logger.debug(f"MM result: {outcome} profit={profit:+.2f} daily_pnl={self._daily_pnl:+.2f}")

    def check_daily_limits(self, balance: float) -> dict:
        if self._day_start <= 0:
            return {"stop_loss": False, "take_profit": False}
        loss_pct  = (self._day_start - balance) / self._day_start * 100
        gain_pct  = (balance - self._day_start) / self._day_start * 100
        return {
            "stop_loss":   loss_pct  >= DAILY_STOP_LOSS_PCT,
            "take_profit": gain_pct  >= DAILY_TAKE_PROFIT_PCT,
            "loss_pct":    loss_pct,
            "gain_pct":    gain_pct,
        }

    @property
    def daily_stats(self) -> dict:
        return {
            "trades": self._daily_trades,
            "wins":   self._daily_wins,
            "pnl":    self._daily_pnl,
            "win_rate": self._daily_wins / self._daily_trades if self._daily_trades else 0,
        }
