"""
Indicadores técnicos calculados sobre un DataFrame OHLCV.
"""
import numpy as np
import pandas as pd


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(close: pd.Series):
    fast  = _ema(close, 12)
    slow  = _ema(close, 26)
    line  = fast - slow
    signal = _ema(line, 9)
    return line, signal, line - signal


def _bollinger(close: pd.Series, period: int = 20, std: float = 2.0):
    mid   = close.rolling(period).mean()
    sigma = close.rolling(period).std()
    return mid + std * sigma, mid, mid - std * sigma


def _stoch(high, low, close, k=14, d=3):
    low_k  = low.rolling(k).min()
    high_k = high.rolling(k).max()
    pct_k  = 100 * (close - low_k) / (high_k - low_k).replace(0, np.nan)
    pct_d  = pct_k.rolling(d).mean()
    return pct_k, pct_d


def _atr(high, low, close, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _cci(high, low, close, period: int = 20) -> pd.Series:
    tp  = (high + low + close) / 3
    ma  = tp.rolling(period).mean()
    md  = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - ma) / (0.015 * md.replace(0, np.nan))


def _willr(high, low, close, period: int = 14) -> pd.Series:
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    return -100 * (hh - close) / (hh - ll).replace(0, np.nan)


def _adx(high, low, close, period: int = 14) -> pd.Series:
    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr       = _atr(high, low, close, 1)
    plus_di  = 100 * plus_dm.ewm(span=period, adjust=False).mean() / tr.ewm(span=period, adjust=False).mean().replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / tr.ewm(span=period, adjust=False).mean().replace(0, np.nan)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(span=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    df["rsi"]    = _rsi(c)
    df["macd"], df["macd_signal"], df["macd_hist"] = _macd(c)
    df["bb_up"], df["bb_mid"], df["bb_low"]        = _bollinger(c)
    df["stoch_k"], df["stoch_d"]                   = _stoch(h, l, c)
    df["ema9"]   = _ema(c, 9)
    df["ema21"]  = _ema(c, 21)
    df["ema50"]  = _ema(c, 50)
    df["ema200"] = _ema(c, 200)
    df["atr"]    = _atr(h, l, c)
    df["cci"]    = _cci(h, l, c)
    df["willr"]  = _willr(h, l, c)
    df["adx"]    = _adx(h, l, c)
    df["obv"]    = (np.sign(c.diff()) * v).cumsum()

    df["body_ratio"] = (c - df["open"]).abs() / (h - l).replace(0, np.nan)
    df["is_bullish"] = (c > df["open"]).astype(int)
    df["close_pct"]  = c.pct_change()

    return df


def generate_signal(df: pd.DataFrame) -> dict:
    if len(df) < 2:
        return {"signal": None, "confidence": 0, "reasons": []}

    r     = df.iloc[-1]
    score = 0.0
    reasons: list[str] = []

    # RSI
    if r.rsi < 30:
        score += 1.0; reasons.append("RSI sobrevendido")
    elif r.rsi > 70:
        score -= 1.0; reasons.append("RSI sobrecomprado")

    # MACD
    if r.macd > r.macd_signal and r.macd_hist > 0:
        score += 0.8; reasons.append("MACD alcista")
    elif r.macd < r.macd_signal and r.macd_hist < 0:
        score -= 0.8; reasons.append("MACD bajista")

    # Bollinger
    if r.close <= r.bb_low:
        score += 0.6; reasons.append("Precio en BB inferior")
    elif r.close >= r.bb_up:
        score -= 0.6; reasons.append("Precio en BB superior")

    # Stoch
    if r.stoch_k < 20 and r.stoch_k > r.stoch_d:
        score += 0.5; reasons.append("Stoch cruce alcista")
    elif r.stoch_k > 80 and r.stoch_k < r.stoch_d:
        score -= 0.5; reasons.append("Stoch cruce bajista")

    # EMA stack
    if r.ema9 > r.ema21 > r.ema50:
        score += 0.6; reasons.append("EMAs alineadas alcistas")
    elif r.ema9 < r.ema21 < r.ema50:
        score -= 0.6; reasons.append("EMAs alineadas bajistas")

    signal = "call" if score > 1.0 else ("put" if score < -1.0 else None)
    conf   = min(abs(score) / 4.0, 1.0)

    return {"signal": signal, "confidence": conf, "score": score, "reasons": reasons}
