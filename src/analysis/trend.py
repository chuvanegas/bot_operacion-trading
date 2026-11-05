"""
Detección de tendencia por pendiente EMA y estructura HH/HL.
"""
import numpy as np
import pandas as pd


def get_trend_strength(df: pd.DataFrame) -> dict:
    if len(df) < 50:
        return {"trend_short": "sideways", "trend_long": "sideways",
                "adx": 0.0, "strong_trend": False}

    ema9  = df["ema9"].iloc[-1]  if "ema9"  in df.columns else df["close"].ewm(span=9).mean().iloc[-1]
    ema21 = df["ema21"].iloc[-1] if "ema21" in df.columns else df["close"].ewm(span=21).mean().iloc[-1]
    ema50 = df["ema50"].iloc[-1] if "ema50" in df.columns else df["close"].ewm(span=50).mean().iloc[-1]

    if ema9 > ema21:
        trend_short = "up"
    elif ema9 < ema21:
        trend_short = "down"
    else:
        trend_short = "sideways"

    if ema21 > ema50:
        trend_long = "up"
    elif ema21 < ema50:
        trend_long = "down"
    else:
        trend_long = "sideways"

    highs = df["high"].iloc[-20:].values
    lows  = df["low"].iloc[-20:].values
    hh    = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
    hl    = sum(1 for i in range(1, len(lows))  if lows[i]  > lows[i-1])
    lh    = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
    ll    = sum(1 for i in range(1, len(lows))  if lows[i]  < lows[i-1])

    adx = float(df["adx"].iloc[-1]) if "adx" in df.columns else 0.0

    return {
        "trend_short": trend_short,
        "trend_long":  trend_long,
        "adx":         adx,
        "strong_trend": adx > 25,
        "hh_hl": hh >= 12 and hl >= 12,
        "ll_lh": lh >= 12 and ll >= 12,
    }
