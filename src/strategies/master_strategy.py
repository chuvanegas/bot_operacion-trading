"""
Estrategia maestra: 6 capas con PCRV4 como capa de mayor peso.

  Capa 1: Indicadores técnicos (W=1.0)
  Capa 2: Price Action (W=1.2)
  Capa 3: S/R context (bonus/penalidad)
  Capa 4: Tendencia (penalidad si va contra)
  Capa 5: ML Ensemble (W=0.8)
  Capa 6: PCRV4 (W=1.3 — mayor peso)
"""
import logging
import pandas as pd
from src.analysis.indicators       import add_indicators, generate_signal
from src.analysis.price_action     import analyze_price_action
from src.analysis.support_resistance import get_sr_context
from src.analysis.trend            import get_trend_strength
from src.strategies.ml_model       import MLPredictor
from src.strategies.pcrv4          import analyze_pcrv4

logger = logging.getLogger(__name__)

W_TECH  = 1.0
W_PA    = 1.2
W_ML    = 0.8
W_PCRV4 = 1.3

SR_BONUS     = 0.30
TREND_PENALTY = 0.70
MIN_SCORE     = 1.5


def _direction_score(signal: str | None, conf: float, weight: float) -> float:
    if signal == "call":  return  conf * weight
    if signal == "put":   return -conf * weight
    return 0.0


class MasterStrategy:
    def __init__(self):
        self.ml = MLPredictor()

    def train_ml(self, df: pd.DataFrame):
        df = add_indicators(df.copy())
        self.ml.train(df)

    def analyze(self, df: pd.DataFrame) -> dict:
        df = add_indicators(df.copy())

        # ── Capas ────────────────────────────────────────────────────────────
        tech   = generate_signal(df)
        pa     = analyze_price_action(df)
        sr     = get_sr_context(df)
        trend  = get_trend_strength(df)
        ml_sig, ml_conf = self.ml.predict(df)
        pcrv4  = analyze_pcrv4(df, sr_context=sr)

        score = 0.0
        score += _direction_score(tech.get("signal"),  tech.get("confidence", 0),  W_TECH)
        score += _direction_score(pa.get("signal"),    pa.get("confidence", 0),    W_PA)
        score += _direction_score(ml_sig,              ml_conf,                    W_ML)
        score += _direction_score(pcrv4.get("signal"), pcrv4.get("confidence", 0), W_PCRV4)

        signal_direction = "call" if score > 0 else "put" if score < 0 else None

        # ── Capa 3: S/R bonus ─────────────────────────────────────────────────
        if signal_direction == "call" and sr.get("at_support"):
            score += SR_BONUS
        elif signal_direction == "put" and sr.get("at_resistance"):
            score += SR_BONUS
        elif signal_direction == "call" and sr.get("at_resistance"):
            score -= SR_BONUS
        elif signal_direction == "put" and sr.get("at_support"):
            score -= SR_BONUS

        # ── Capa 4: Tendencia penalidad ───────────────────────────────────────
        t_short = trend.get("trend_short", "sideways")
        if signal_direction == "call" and t_short == "down" and trend.get("strong_trend"):
            score *= TREND_PENALTY
        elif signal_direction == "put" and t_short == "up" and trend.get("strong_trend"):
            score *= TREND_PENALTY

        # ── Señal final ───────────────────────────────────────────────────────
        abs_score = abs(score)
        if abs_score < MIN_SCORE:
            final_signal = None
        else:
            final_signal = "call" if score > 0 else "put"

        confidence = min(abs_score / 6.0, 1.0)

        reasons = []
        if tech.get("signal") == final_signal:
            reasons += tech.get("reasons", [])[:2]
        if pa.get("signal") == final_signal:
            reasons.append(f"PA: {', '.join(pa.get('patterns', []))}")
        if pcrv4.get("pattern"):
            reasons.append(pcrv4.get("reason", "PCRV4"))
        if ml_sig == final_signal:
            reasons.append(f"ML: {ml_conf:.0%}")

        return {
            "signal":     final_signal,
            "confidence": confidence,
            "score":      round(score, 3),
            "reasons":    reasons,
            "pcrv4":      pcrv4,
            "trend":      trend,
            "sr":         sr,
            "tech":       tech,
            "pa":         pa,
            "ml":         {"signal": ml_sig, "confidence": ml_conf},
        }
