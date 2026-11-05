"""
Ensemble ML: RandomForest + XGBoost con VotingClassifier (soft).
"""
import os
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = "models/trained/ensemble_model.joblib"
FEATURES   = [
    "rsi", "macd", "macd_hist", "stoch_k", "stoch_d",
    "ema9", "ema21", "ema50", "atr", "cci", "willr", "adx",
    "body_ratio", "is_bullish", "close_pct",
    "bb_up", "bb_mid", "bb_low", "obv", "volume"
]


class MLPredictor:
    def __init__(self):
        self.model    = None
        self.trained  = False
        self._load()

    def _load(self):
        if not os.path.exists(MODEL_PATH):
            return
        try:
            import joblib
            self.model   = joblib.load(MODEL_PATH)
            self.trained = True
            logger.info("Modelo ML cargado")
        except Exception as e:
            logger.warning(f"No se pudo cargar modelo: {e}")

    def _build(self):
        try:
            from sklearn.ensemble import RandomForestClassifier, VotingClassifier
            from xgboost import XGBClassifier
            rf  = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            xgb = XGBClassifier(n_estimators=100, learning_rate=0.1, random_state=42,
                                 eval_metric="logloss", verbosity=0)
            return VotingClassifier([("rf", rf), ("xgb", xgb)], voting="soft")
        except ImportError as e:
            logger.warning(f"ML libs no disponibles: {e}")
            return None

    def train(self, df: pd.DataFrame) -> bool:
        try:
            from sklearn.model_selection import cross_val_score
            import joblib

            df = df.dropna(subset=FEATURES + ["close"])
            if len(df) < 100:
                logger.warning("Datos insuficientes para entrenar ML")
                return False

            # Etiqueta: 1=call (sube), 0=put (baja) en siguiente vela
            df = df.copy()
            df["label"] = (df["close"].shift(-1) > df["close"]).astype(int)
            df = df.dropna(subset=["label"])

            X = df[FEATURES].values
            y = df["label"].values

            model = self._build()
            if model is None:
                return False

            scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
            logger.info(f"ML CV accuracy: {scores.mean():.3f} ± {scores.std():.3f}")

            model.fit(X, y)
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            joblib.dump(model, MODEL_PATH)
            self.model   = model
            self.trained = True
            logger.info("Modelo ML entrenado y guardado")
            return True
        except Exception as e:
            logger.error(f"Error entrenando ML: {e}")
            return False

    def predict(self, df: pd.DataFrame) -> tuple[str | None, float]:
        if not self.trained or self.model is None:
            return None, 0.0
        try:
            row = df[FEATURES].iloc[-1:].fillna(0)
            proba = self.model.predict_proba(row)[0]
            if proba[1] > 0.60:
                return "call", float(proba[1])
            if proba[0] > 0.60:
                return "put", float(proba[0])
            return None, float(max(proba))
        except Exception as e:
            logger.warning(f"ML predict error: {e}")
            return None, 0.0
