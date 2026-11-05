"""
Patrones de price action para análisis técnico.
"""
import numpy as np
import pandas as pd


def _body(c):   return abs(c["close"] - c["open"])
def _range(c):  return c["high"] - c["low"]
def _bull(c):   return c["close"] > c["open"]
def _bear(c):   return c["close"] < c["open"]


def _pin_bar(c) -> str | None:
    body  = _body(c)
    rng   = _range(c)
    if rng == 0:
        return None
    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    if lower_wick > 2 * body and body / rng < 0.3:
        return "call"
    if upper_wick > 2 * body and body / rng < 0.3:
        return "put"
    return None


def _inside_bar(prev, curr) -> str | None:
    if curr["high"] < prev["high"] and curr["low"] > prev["low"]:
        return "call" if _bull(prev) else "put"
    return None


def _three_inside(candles) -> str | None:
    a, b, c = candles[-3], candles[-2], candles[-1]
    if _bear(a) and _bull(b) and _bull(c):
        if b["open"] > a["close"] and b["close"] < a["open"]:
            if c["close"] > a["open"]:
                return "call"
    if _bull(a) and _bear(b) and _bear(c):
        if b["open"] < a["close"] and b["close"] > a["open"]:
            if c["close"] < a["open"]:
                return "put"
    return None


def _three_candle_reversal(candles) -> str | None:
    a, b, c = candles[-3], candles[-2], candles[-1]
    if _bear(a) and _bear(b) and _bull(c):
        if c["close"] > b["open"]:
            return "call"
    if _bull(a) and _bull(b) and _bear(c):
        if c["close"] < b["open"]:
            return "put"
    return None


def _strong_engulfing(prev, curr) -> str | None:
    if _bear(prev) and _bull(curr):
        if curr["open"] <= prev["close"] and curr["close"] >= prev["open"]:
            return "call"
    if _bull(prev) and _bear(curr):
        if curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
            return "put"
    return None


def _marubozu(c) -> str | None:
    body = _body(c)
    rng  = _range(c)
    if rng > 0 and body / rng > 0.85:
        return "call" if _bull(c) else "put"
    return None


PATTERN_WEIGHTS = {
    "pin_bar":            0.80,
    "inside_bar":         0.75,
    "three_inside":       0.77,
    "three_candle_rev":   0.80,
    "strong_engulfing":   0.78,
    "marubozu":           0.72,
}


def analyze_price_action(df: pd.DataFrame) -> dict:
    if len(df) < 3:
        return {"signal": None, "confidence": 0, "patterns": []}

    rows = df.to_dict("records")
    curr, prev = rows[-1], rows[-2]

    signals: list[tuple[str, float, str]] = []

    s = _pin_bar(curr)
    if s: signals.append((s, PATTERN_WEIGHTS["pin_bar"], "pin_bar"))

    s = _inside_bar(prev, curr)
    if s: signals.append((s, PATTERN_WEIGHTS["inside_bar"], "inside_bar"))

    s = _three_inside(rows)
    if s: signals.append((s, PATTERN_WEIGHTS["three_inside"], "three_inside"))

    s = _three_candle_reversal(rows)
    if s: signals.append((s, PATTERN_WEIGHTS["three_candle_rev"], "three_candle_rev"))

    s = _strong_engulfing(prev, curr)
    if s: signals.append((s, PATTERN_WEIGHTS["strong_engulfing"], "strong_engulfing"))

    s = _marubozu(curr)
    if s: signals.append((s, PATTERN_WEIGHTS["marubozu"], "marubozu"))

    if not signals:
        return {"signal": None, "confidence": 0, "patterns": []}

    call_conf = sum(c for sig, c, _ in signals if sig == "call")
    put_conf  = sum(c for sig, c, _ in signals if sig == "put")

    if call_conf > put_conf and call_conf > 0.5:
        return {"signal": "call", "confidence": min(call_conf, 1.0),
                "patterns": [n for _, _, n in signals if _ == n]}
    if put_conf > call_conf and put_conf > 0.5:
        return {"signal": "put", "confidence": min(put_conf, 1.0),
                "patterns": [n for _, _, n in signals if _ == n]}
    return {"signal": None, "confidence": 0, "patterns": [n for _, _, n in signals]}
