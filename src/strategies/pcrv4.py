"""
PCRV4 — Estrategia de las 4 velas.

Reglas exactas de los ejercicios del docx:
  c1, c2, c3 = preparación (≥2 en la dirección + 1 contraria/doji)
  c4         = ruptura fuerte (body Y range > todas las prep; en la dirección)
  c5         = confirmación  (mantiene impulso; close dentro del 0.15% de c4)

Entradas anticipadas (docx imagen 9):
  - AL 25% del body de c4 → entrada agresiva
  - AL 50% del body de c4 → entrada estándar

ZONA FUERTE: descarta la señal aunque el patrón sea válido.
"""
import pandas as pd
from typing import Optional


def _body(o, c):        return abs(c - o)
def _range_(h, l):      return h - l
def _is_bull(o, c):     return c > o
def _is_bear(o, c):     return c < o
def _is_doji(o, c, h, l): return _body(o, c) / (_range_(h, l) or 1) < 0.15


def detect_pcrv4(df: pd.DataFrame, idx: int) -> Optional[str]:
    """Detecta patrón PCRV4 en idx (c5). Devuelve 'call', 'put' o None."""
    if idx < 4:
        return None

    c1 = df.iloc[idx - 4]
    c2 = df.iloc[idx - 3]
    c3 = df.iloc[idx - 2]
    c4 = df.iloc[idx - 1]
    c5 = df.iloc[idx]

    for c in (c1, c2, c3, c4, c5):
        if pd.isna(c["high"]) or pd.isna(c["low"]):
            return None

    # ── Determinar dirección ─────────────────────────────────────────────────
    prep_bulls = sum(_is_bull(c["open"], c["close"]) for c in (c1, c2, c3))
    prep_bears = sum(_is_bear(c["open"], c["close"]) for c in (c1, c2, c3))

    if prep_bulls >= 2:
        direction = "call"
    elif prep_bears >= 2:
        direction = "put"
    else:
        return None

    # ── Verificar vela contraria/doji en preparación ─────────────────────────
    prep = [c1, c2, c3]
    if direction == "call":
        contrary = sum(1 for c in prep if _is_bear(c["open"], c["close"]) or
                       _is_doji(c["open"], c["close"], c["high"], c["low"]))
    else:
        contrary = sum(1 for c in prep if _is_bull(c["open"], c["close"]) or
                       _is_doji(c["open"], c["close"], c["high"], c["low"]))

    if contrary < 1:
        return None

    # ── c4: ruptura fuerte ───────────────────────────────────────────────────
    c4_body  = _body(c4["open"], c4["close"])
    c4_range = _range_(c4["high"], c4["low"])

    if direction == "call" and not _is_bull(c4["open"], c4["close"]):
        return None
    if direction == "put"  and not _is_bear(c4["open"], c4["close"]):
        return None

    max_prep_body  = max(_body(c["open"], c["close"]) for c in prep)
    max_prep_range = max(_range_(c["high"], c["low"]) for c in prep)

    if c4_body <= max_prep_body or c4_range <= max_prep_range:
        return None

    # ── c5: confirmación ─────────────────────────────────────────────────────
    if direction == "call":
        # c5 cierra dentro del 0.15% superior del body de c4
        threshold = c4["close"] * 0.0015
        if not (c5["close"] >= c4["close"] - threshold):
            return None
    else:
        threshold = c4["close"] * 0.0015
        if not (c5["close"] <= c4["close"] + threshold):
            return None

    return direction


def get_entry_levels(df: pd.DataFrame, idx: int, direction: str) -> dict:
    """Calcula niveles de entrada al 25% y 50% del body de c4 (entradas anticipadas)."""
    if idx < 1:
        return {}
    c4 = df.iloc[idx - 1]
    body = _body(c4["open"], c4["close"])
    if direction == "call":
        entry_25 = c4["open"] + body * 0.25
        entry_50 = c4["open"] + body * 0.50
    else:
        entry_25 = c4["open"] - body * 0.25
        entry_50 = c4["open"] - body * 0.50
    return {"entry_25pct": entry_25, "entry_50pct": entry_50, "c4_body": body}


def analyze_pcrv4(df: pd.DataFrame, sr_context: Optional[dict] = None) -> dict:
    """Analiza PCRV4 en el último índice. Aplica regla ZONA FUERTE."""
    if len(df) < 5:
        return {"signal": None, "confidence": 0, "reason": "Datos insuficientes", "pattern": False}

    idx = len(df) - 1
    direction = detect_pcrv4(df, idx)

    if direction is None:
        return {"signal": None, "confidence": 0, "reason": "Sin patrón PCRV4", "pattern": False}

    # Confianza base
    confidence = 0.80

    # ── Regla ZONA FUERTE (descarta la señal) ────────────────────────────────
    if sr_context:
        if direction == "call" and sr_context.get("at_resistance"):
            return {"signal": None, "confidence": 0,
                    "reason": "ZONA FUERTE: resistencia bloquea CALL", "pattern": True}
        if direction == "put"  and sr_context.get("at_support"):
            return {"signal": None, "confidence": 0,
                    "reason": "ZONA FUERTE: soporte bloquea PUT", "pattern": True}

        # Bonificación S/R confirma
        if direction == "call" and sr_context.get("at_support"):
            confidence = 0.88
        elif direction == "put" and sr_context.get("at_resistance"):
            confidence = 0.88

        # Penalización S/R opuesto cercano (< 0.15%)
        dist_opp = (sr_context.get("dist_resistance", 1.0) if direction == "call"
                    else sr_context.get("dist_support", 1.0))
        if dist_opp < 0.0015:
            confidence *= 0.75

    entry = get_entry_levels(df, idx, direction)

    return {
        "signal":     direction,
        "confidence": confidence,
        "reason":     f"PCRV4 {direction.upper()} confirmado",
        "pattern":    True,
        "entry_levels": entry,
    }
