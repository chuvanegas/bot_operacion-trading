"""
Risk Gate — inspirado en trader-risk, adaptado para opciones binarias IQ Option.

Tres puertas antes de operar:
  1. REGLAS — condiciones técnicas (confianza, tendencia, S/R, liquidez)
  2. LÍMITES — capital, stop loss, take profit, horario de mercado
  3. PCRV4 — si está activo, debe confirmar o al menos no contradecir

PASS = puede pasar a la siguiente puerta
BLOCK = se detiene ahí, no hay forma de sobrepasar
"""
from datetime import datetime
from typing import Optional
from config.settings import (
    MIN_CONFIDENCE, DAILY_STOP_LOSS_PCT, DAILY_TAKE_PROFIT_PCT, BASE_AMOUNT
)


class Gate:
    def __init__(self, name: str, passed: bool, reason: str):
        self.name = name
        self.passed = passed
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "gate": self.name,
            "result": "PASS" if self.passed else "BLOCK",
            "reason": self.reason,
        }


class RiskGate:
    def __init__(self):
        self.daily_trades = 0
        self.last_trade_signal = None

    def check(self, analysis: dict, balance: float, day_start: float,
              amount: float, asset_open: bool) -> dict:
        gates = []

        # ── Puerta 1: Señal válida ────────────────────────────────────────────
        signal = analysis.get("signal")
        conf = analysis.get("confidence", 0)
        score = analysis.get("score", 0)

        if signal is None:
            gates.append(Gate("SEÑAL", False, "Sin señal — no hay dirección clara"))
        elif conf < MIN_CONFIDENCE:
            gates.append(Gate("SEÑAL", False,
                              f"Confianza {conf:.1%} < mínimo {MIN_CONFIDENCE:.1%}"))
        else:
            gates.append(Gate("SEÑAL", True,
                               f"{signal.upper()} | conf={conf:.1%} | score={score:.2f}"))

        # ── Puerta 2: Mercado abierto ─────────────────────────────────────────
        gates.append(Gate("MERCADO", asset_open,
                           "Activo disponible" if asset_open else "Activo cerrado en este momento"))

        # ── Puerta 3: Capital ─────────────────────────────────────────────────
        if amount > balance * 0.20:
            gates.append(Gate("CAPITAL", False,
                               f"Monto ${amount:.2f} supera 20% del balance ${balance:.2f}"))
        elif balance < BASE_AMOUNT:
            gates.append(Gate("CAPITAL", False, f"Balance ${balance:.2f} insuficiente"))
        else:
            gates.append(Gate("CAPITAL", True, f"Monto ${amount:.2f} aprobado sobre balance ${balance:.2f}"))

        # ── Puerta 4: Límites diarios ─────────────────────────────────────────
        if day_start > 0:
            loss_pct = (day_start - balance) / day_start * 100
            gain_pct = (balance - day_start) / day_start * 100
            if loss_pct >= DAILY_STOP_LOSS_PCT:
                gates.append(Gate("LÍMITE DIARIO", False,
                                   f"Stop loss diario alcanzado: -{loss_pct:.1f}%"))
            elif gain_pct >= DAILY_TAKE_PROFIT_PCT:
                gates.append(Gate("LÍMITE DIARIO", False,
                                   f"Take profit diario alcanzado: +{gain_pct:.1f}%"))
            else:
                pnl = balance - day_start
                gates.append(Gate("LÍMITE DIARIO", True,
                                   f"P&L hoy: {pnl:+.2f} | SL en -{DAILY_STOP_LOSS_PCT}% TP en +{DAILY_TAKE_PROFIT_PCT}%"))

        # ── Puerta 5: PCRV4 no contradice ────────────────────────────────────
        pcrv4 = analysis.get("pcrv4", {})
        pcrv4_signal = pcrv4.get("signal")
        if pcrv4_signal is not None and pcrv4_signal != signal:
            gates.append(Gate("PCRV4", False,
                               f"PCRV4 contradice: da {pcrv4_signal.upper()} pero señal es {signal.upper() if signal else 'ninguna'}"))
        elif pcrv4_signal == signal:
            gates.append(Gate("PCRV4", True,
                               f"PCRV4 confirma {signal.upper()} (conf={pcrv4.get('confidence', 0):.2f})"))
        else:
            gates.append(Gate("PCRV4", True, "PCRV4 sin patrón — señal pasa sin refuerzo"))

        # ── Resultado final ───────────────────────────────────────────────────
        all_pass = all(g.passed for g in gates)
        first_block = next((g for g in gates if not g.passed), None)

        return {
            "verdict": "PASS" if all_pass else "BLOCK",
            "gates": [g.to_dict() for g in gates],
            "block_reason": first_block.reason if first_block else None,
            "can_trade": all_pass,
            "signal": signal,
            "confidence": conf,
            "timestamp": datetime.now().isoformat(),
        }
