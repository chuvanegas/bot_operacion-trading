"""
Dashboard de terminal — muestra estado del bot en tiempo real.
"""
import os
import logging

logger = logging.getLogger(__name__)


class Display:
    def __init__(self):
        self._balance_start = 0.0
        self._balance       = 0.0

    def set_balance(self, start: float, current: float):
        self._balance_start = start
        self._balance       = current

    def update(self, analysis: dict, gate: dict, balance: float,
               daily: dict, history: list):
        self._balance = balance
        try:
            os.system("clear")
        except Exception:
            print("\n" * 3)

        signal  = analysis.get("signal") or "—"
        conf    = analysis.get("confidence", 0)
        score   = analysis.get("score", 0)
        pcrv4   = analysis.get("pcrv4", {})
        trend   = analysis.get("trend", {})

        pcrv4_str = "✅ ACTIVO" if pcrv4.get("pattern") else "⬜ sin patrón"
        gate_str  = "🟢 PASS" if gate.get("verdict") == "PASS" else f"🔴 BLOCK: {gate.get('block_reason','')}"

        print("=" * 58)
        print(" IQ Option Bot — PCRV4 Strategy")
        print("=" * 58)
        print(f" Balance  : ${balance:.2f}  (inicio: ${self._balance_start:.2f})")
        print(f" P&L hoy  : ${daily.get('pnl', 0):+.2f}  "
              f"({daily.get('win_rate', 0):.0%} WR — {daily.get('trades', 0)} ops)")
        print("-" * 58)
        icon = "🟢" if signal == "call" else ("🔴" if signal == "put" else "⬜")
        print(f" Señal    : {icon} {signal.upper():<6}  conf={conf:.1%}  score={score:.2f}")
        print(f" PCRV4    : {pcrv4_str}")
        print(f" Tendencia: {trend.get('trend_short','?')} / {trend.get('trend_long','?')}  ADX={trend.get('adx',0):.1f}")
        print(f" Risk Gate: {gate_str}")
        print("-" * 58)
        for g in gate.get("gates", []):
            icon_g = "✅" if g["result"] == "PASS" else "❌"
            print(f"  {icon_g} {g['gate']:<18} {g['reason'][:35]}")
        print("-" * 58)
        print(" Historial reciente:")
        for h in reversed(history[-5:]):
            icon_h = "✅" if h["outcome"] == "win" else "❌"
            print(f"  {icon_h} {h['time']} {h['signal'].upper():<4} {h['profit']:+.2f}")
        print("=" * 58)
