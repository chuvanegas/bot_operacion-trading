"""
Loop principal de trading. Integra RiskGate y Alerts.
"""
import time
import logging
from datetime import datetime, date

from config.settings import ASSET, OPTION_TYPE, EXPIRY_SECONDS, PAYOUT_RATE
from src.broker.iqoption_client     import IQOptionClient
from src.strategies.master_strategy import MasterStrategy
from src.risk.money_management       import MoneyManager
from src.risk.risk_gate              import RiskGate
from src.bot.alerts                  import alert_signal, alert_result, alert_daily_limit, reset_daily
from src.bot.display                 import Display

logger = logging.getLogger(__name__)

CANDLE_INTERVAL  = 60      # 1 minuto
CANDLE_COUNT     = 300
RETRAIN_EVERY    = 50      # operaciones antes de re-entrenar ML


class Trader:
    def __init__(self):
        self.client   = IQOptionClient()
        self.strategy = MasterStrategy()
        self.mm       = MoneyManager()
        self.gate     = RiskGate()
        self.display  = Display()
        self._trade_count = 0
        self._history: list = []

    # ── Inicio ────────────────────────────────────────────────────────────────
    def start(self):
        if not self.client.connect():
            logger.error("No se pudo conectar a IQ Option")
            return

        balance = self.client.get_balance()
        self.mm.reset_day(balance)
        self.display.set_balance(balance, balance)
        logger.info(f"Balance inicial: {balance:.2f}")

        # Entrenar ML inicial
        df_init = self.client.get_candles(ASSET, CANDLE_INTERVAL, CANDLE_COUNT)
        self.strategy.train_ml(df_init)

        self._loop()

    # ── Loop principal ────────────────────────────────────────────────────────
    def _loop(self):
        last_day = date.today()

        while True:
            try:
                # Reset diario
                today = date.today()
                if today != last_day:
                    balance = self.client.get_balance()
                    self.mm.reset_day(balance)
                    reset_daily()
                    last_day = today
                    logger.info("Reset diario ejecutado")

                # Obtener datos
                df      = self.client.get_candles(ASSET, CANDLE_INTERVAL, CANDLE_COUNT)
                balance = self.client.get_balance()
                price   = float(df["close"].iloc[-1])

                # Analizar
                analysis = self.strategy.analyze(df)
                amount   = self.mm.get_amount()
                is_open  = self.client.is_asset_open(ASSET, OPTION_TYPE)

                # Risk Gate
                gate_result = self.gate.check(
                    analysis=analysis,
                    balance=balance,
                    day_start=self.mm._day_start,
                    amount=amount,
                    asset_open=is_open,
                )

                # Display
                self.display.update(analysis, gate_result, balance,
                                    self.mm.daily_stats, self._history[-10:])

                # Límites diarios
                limits = self.mm.check_daily_limits(balance)
                if limits["stop_loss"]:
                    alert_daily_limit("stop_loss", balance, self.mm._day_start)
                    logger.warning("Stop loss diario alcanzado — deteniendo bot")
                    break
                if limits["take_profit"]:
                    alert_daily_limit("take_profit", balance, self.mm._day_start)
                    logger.info("Take profit diario alcanzado — deteniendo bot")
                    break

                # Operar solo si pasa todas las puertas
                if gate_result["can_trade"]:
                    signal = gate_result["signal"]
                    self._place_trade(signal, amount, analysis, price)

                # Re-entrenar ML cada N operaciones
                if self._trade_count > 0 and self._trade_count % RETRAIN_EVERY == 0:
                    logger.info("Re-entrenando modelo ML…")
                    self.strategy.train_ml(df)

                time.sleep(CANDLE_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Bot detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en loop: {e}", exc_info=True)
                time.sleep(10)

    # ── Colocar operación ─────────────────────────────────────────────────────
    def _place_trade(self, signal: str, amount: float, analysis: dict, price: float):
        pcrv4   = analysis.get("pcrv4", {})
        reasons = analysis.get("reasons", [])
        conf    = analysis.get("confidence", 0)

        alert_signal(signal, ASSET, conf, reasons,
                     pcrv4_active=pcrv4.get("pattern", False), price=price)

        ok, order_id = self.client.buy(ASSET, amount, signal, EXPIRY_SECONDS, OPTION_TYPE)
        if not ok:
            logger.error(f"Error colocando orden {signal.upper()}")
            return

        logger.info(f"OPERACIÓN: {signal.upper()} {ASSET} ${amount:.2f} | id={order_id}")
        time.sleep(EXPIRY_SECONDS + 2)

        outcome, profit = self.client.check_win(order_id, OPTION_TYPE)
        balance_now     = self.client.get_balance()

        self.mm.register_result(outcome, profit)
        self.gate.daily_trades += 1
        self._trade_count += 1

        self._history.append({
            "time":    datetime.now().strftime("%H:%M"),
            "signal":  signal,
            "outcome": outcome,
            "profit":  profit,
            "balance": balance_now,
        })

        alert_result(signal, ASSET, outcome, profit, balance_now)
        logger.info(f"RESULTADO: {outcome.upper()} profit={profit:+.2f} balance={balance_now:.2f}")
