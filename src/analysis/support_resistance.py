"""
Zonas de soporte y resistencia por pivotes con clustering.
"""
import numpy as np
import pandas as pd
from typing import List


def _pivot_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> List[float]:
    highs = []
    for i in range(left, len(df) - right):
        if all(df["high"].iloc[i] >= df["high"].iloc[i - j] for j in range(1, left + 1)) \
           and all(df["high"].iloc[i] >= df["high"].iloc[i + j] for j in range(1, right + 1)):
            highs.append(float(df["high"].iloc[i]))
    return highs


def _pivot_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> List[float]:
    lows = []
    for i in range(left, len(df) - right):
        if all(df["low"].iloc[i] <= df["low"].iloc[i - j] for j in range(1, left + 1)) \
           and all(df["low"].iloc[i] <= df["low"].iloc[i + j] for j in range(1, right + 1)):
            lows.append(float(df["low"].iloc[i]))
    return lows


def _cluster(levels: List[float], tol_pct: float = 0.002) -> List[float]:
    if not levels:
        return []
    levels = sorted(levels)
    clusters, group = [], [levels[0]]
    for lv in levels[1:]:
        if abs(lv - group[-1]) / group[-1] <= tol_pct:
            group.append(lv)
        else:
            clusters.append(np.mean(group))
            group = [lv]
    clusters.append(np.mean(group))
    return clusters


def get_sr_zones(df: pd.DataFrame) -> dict:
    resistances = _cluster(_pivot_highs(df))
    supports    = _cluster(_pivot_lows(df))
    return {"resistance": resistances, "support": supports}


def get_sr_context(df: pd.DataFrame) -> dict:
    if len(df) < 10:
        return {"at_support": False, "at_resistance": False,
                "dist_support": 1.0, "dist_resistance": 1.0}

    zones  = get_sr_zones(df)
    price  = float(df["close"].iloc[-1])
    atr    = float(df["high"].iloc[-20:].mean() - df["low"].iloc[-20:].mean())
    tol    = atr * 0.5 if atr > 0 else price * 0.001

    at_sup = any(abs(price - s) < tol for s in zones["support"])
    at_res = any(abs(price - r) < tol for r in zones["resistance"])

    dist_s = min((abs(price - s) / price for s in zones["support"]),  default=1.0)
    dist_r = min((abs(price - r) / price for r in zones["resistance"]), default=1.0)

    return {
        "at_support":    at_sup,
        "at_resistance": at_res,
        "dist_support":  dist_s,
        "dist_resistance": dist_r,
        "support_levels": zones["support"][-3:],
        "resistance_levels": zones["resistance"][-3:],
    }
