"""
Loop principal — conecta a IQ Option, monitorea y pide aprobación
al usuario via app web (localhost) o Telegram como respaldo.
"""
import time
import asyncio
import logging
from datetime import datetime, date

from config.settings import ASSET, OPTION_TYPE, EXPIRY_SECONDS
from src.broker.iqoption_client     import IQOptionClient
from src.strategies.master_strategy import MasterStrategy
from src.risk.money_management       import MoneyManager
from src.risk.risk_gate              import RiskGate
from src.bot.alerts                  import alert_signal, alert_result, alert_daily_limit, reset_daily
from src.bot.approval                import request_approval as telegram_approval
from src.bot import ws_server

logger = logging.getLogger(__name__)

CANDLE_INTERVAL = 60
CANDLE_COUNT    = 300
RETRAIN_EVERY   = 50


class Trader:
    def __init__(self):
        self.client   = IQOptionClient()
        self.strategy = MasterStrategy()
        self.mm       = MoneyManager()
        self.gate     = RiskGate()
        self._trade_count = 0
        self._history: list = []

    # ── Inicio ────────────────────────────────────────────────────────────────
    def start(self):
        # Iniciar app web
        ws_server.start_server()
        ws_server.update_state(bot_status="CONECTANDO A IQ OPTION…")

        if not self.client.connect():
            ws_server.update_state(bot_status="ERROR: No se pudo conectar a IQ Option",
                                   connected=False)
            logger.error("No se pudo conectar a IQ Option")
            return

        balance = self.client.get_balance()
        self.mm.reset_day(balance)

        from config.settings import USE_DEMO
        ws_server.update_state(
            connected    = True,
            account_type = "PRACTICE" if USE_DEMO else "REAL",
            balance      = balance,
            balance_start= balance,
            bot_status   = "MONITOREANDO",
            asset        = ASSET,
        )

        logger.info(f"✅ Conectado | Balance: ${balance:.2f} | {'DEMO' if USE_DEMO else 'REAL'}")
        logger.info(f"🌐 Abre tu app: http://localhost:8765/app.html  (o abre web/app.html)")

        # Entrenar ML inicial
        try:
            df_init = self.client.get_candles(ASSET, CANDLE_INTERVAL, CANDLE_COUNT)
            self.strategy.train_ml(df_init)
        except Exception as e:
            logger.warning(f"ML inicial no entrenado: {e}")

        self._loop()

    # ── Loop principal ────────────────────────────────────────────────────────
    def _loop(self):
        last_day = date.today()

        while True:
            try:
                today = date.today()
                if today != last_day:
                    balance = self.client.get_balance()
                    self.mm.reset_day(balance)
                    reset_daily()
                    last_day = today

                # ── Datos frescos ─────────────────────────────────────────────
                df      = self.client.get_candles(ASSET, CANDLE_INTERVAL, CANDLE_COUNT)
                balance = self.client.get_balance()
                price   = float(df["close"].iloc[-1])

                # ── Análisis ──────────────────────────────────────────────────
                analysis = self.strategy.analyze(df)
                amount   = self.mm.get_amount()
                is_open  = self.client.is_asset_open(ASSET, OPTION_TYPE)

                gate_result = self.gate.check(
                    analysis   = analysis,
                    balance    = balance,
                    day_start  = self.mm._day_start,
                    amount     = amount,
                    asset_open = is_open,
                )

                pcrv4  = analysis.get("pcrv4", {})
                trend  = analysis.get("trend", {})
                layers = {
                    "tech":  analysis.get("tech",  {}),
                    "pa":    analysis.get("pa",    {}),
                    "ml":    analysis.get("ml",    {}),
                    "pcrv4": pcrv4,
                }

                # ── Actualizar app web ────────────────────────────────────────
                ws_server.update_state(
                    balance    = balance,
                    price      = price,
                    signal     = analysis.get("signal"),
                    confidence = analysis.get("confidence", 0),
                    score      = analysis.get("score", 0),
                    pcrv4      = pcrv4,
                    gates      = gate_result.get("gates", []),
                    verdict    = gate_result.get("verdict", "BLOCK"),
                    block_reason = gate_result.get("block_reason"),
                    trend      = trend,
                    layers     = layers,
                    reasons    = analysis.get("reasons", []),
                    daily      = self.mm.daily_stats,
                    history    = self._history[-20:],
                    pending_approval = False,
                    bot_status = "MONITOREANDO",
                )

                # ── Límites diarios ───────────────────────────────────────────
                limits = self.mm.check_daily_limits(balance)
                if limits["stop_loss"]:
                    alert_daily_limit("stop_loss", balance, self.mm._day_start)
                    ws_server.update_state(bot_status="DETENIDO: Stop loss diario")
                    break
                if limits["take_profit"]:
                    alert_daily_limit("take_profit", balance, self.mm._day_start)
                    ws_server.update_state(bot_status="DETENIDO: Take profit diario ✅")
                    break

                # ── Señal válida → pedir aprobación ───────────────────────────
                if gate_result["can_trade"]:
                    signal  = gate_result["signal"]
                    conf    = analysis.get("confidence", 0)
                    score   = analysis.get("score", 0)
                    reasons = analysis.get("reasons", [])

                    logger.info(f"🔔 Señal: {signal.upper()} conf={conf:.1%} score={score:.2f}")

                    # Marcar como pendiente en la app web
                    ws_server.update_state(
                        pending_approval = True,
                        bot_status       = f"⏳ ESPERANDO TU APROBACIÓN — {signal.upper()}",
                    )

                    # Intentar aprobación por web primero, Telegram como respaldo
                    approved = self._request_approval_hybrid(
                        signal, ASSET, price, conf, score,
                        pcrv4.get("pattern", False), reasons
                    )

                    ws_server.update_state(pending_approval=False)

                    if approved:
                        self._place_trade(signal, amount, analysis, price)
                    else:
                        ws_server.update_state(bot_status="MONITOREANDO — señal descartada")
                        logger.info("Señal descartada — sin aprobación")

                if self._trade_count > 0 and self._trade_count % RETRAIN_EVERY == 0:
                    logger.info("Re-entrenando ML…")
                    self.strategy.train_ml(df)

                time.sleep(CANDLE_INTERVAL)

            except KeyboardInterrupt:
                ws_server.update_state(bot_status="DETENIDO por usuario")
                break
            except Exception as e:
                logger.error(f"Error en loop: {e}", exc_info=True)
                ws_server.update_state(bot_status=f"Error: {e}")
                time.sleep(10)

    # ── Aprobación híbrida (web + Telegram fallback) ──────────────────────────
    def _request_approval_hybrid(self, signal, asset, price, conf, score,
                                  pcrv4_active, reasons) -> bool:
        TIMEOUT = 50

        if ws_server.has_web_client():
            # Hay alguien en la app web → esperar ahí
            logger.info("Esperando aprobación en app web…")
            try:
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(ws_server.wait_for_approval(TIMEOUT))
                loop.close()
                return result
            except Exception as e:
                logger.warning(f"Error esperando web approval: {e}")
                return False
        else:
            # Nadie en la web → usar Telegram
            logger.info("Sin cliente web — usando Telegram para aprobación…")
            return telegram_approval(signal, asset, price, conf, score, pcrv4_active, reasons)

    # ── Colocar operación ─────────────────────────────────────────────────────
    def _place_trade(self, signal: str, amount: float, analysis: dict, price: float):
        pcrv4   = analysis.get("pcrv4", {})
        reasons = analysis.get("reasons", [])
        conf    = analysis.get("confidence", 0)

        ws_server.update_state(bot_status=f"EJECUTANDO {signal.upper()} ${amount:.2f}…")
        alert_signal(signal, ASSET, conf, reasons,
                     pcrv4_active=pcrv4.get("pattern", False), price=price)

        ok, order_id = self.client.buy(ASSET, amount, signal, EXPIRY_SECONDS, OPTION_TYPE)
        if not ok:
            ws_server.update_state(bot_status="ERROR colocando orden")
            return

        logger.info(f"💰 {signal.upper()} ${amount:.2f} ejecutado | id={order_id}")
        ws_server.update_state(bot_status=f"OPERACIÓN ACTIVA — esperando resultado ({EXPIRY_SECONDS}s)…")

        time.sleep(EXPIRY_SECONDS + 2)

        outcome, profit = self.client.check_win(order_id, OPTION_TYPE)
        balance_now     = self.client.get_balance()

        self.mm.register_result(outcome, profit)
        self.gate.daily_trades += 1
        self._trade_count += 1

        entry = {
            "time":    datetime.now().strftime("%H:%M"),
            "signal":  signal,
            "outcome": outcome,
            "profit":  profit,
            "balance": balance_now,
            "conf":    conf,
            "pcrv4":   pcrv4.get("pattern", False),
        }
        self._history.append(entry)

        ws_server.update_state(
            balance  = balance_now,
            daily    = self.mm.daily_stats,
            history  = self._history[-20:],
            bot_status = f"{'✅ WIN' if outcome=='win' else '❌ LOSE'} {signal.upper()} P&L:{profit:+.2f}",
        )

        alert_result(signal, ASSET, outcome, profit, balance_now)
        icon = "✅" if outcome == "win" else "❌"
        logger.info(f"{icon} {outcome.upper()} profit={profit:+.2f} balance=${balance_now:.2f}")
