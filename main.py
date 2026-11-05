"""
Punto de entrada del bot PCRV4 para IQ Option.

Modos:
  python main.py              → bot en vivo
  python main.py --backtest   → backtest sobre datos históricos
  python main.py --train-only → solo entrenar y guardar modelo ML
"""
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Bot PCRV4 IQ Option")
    parser.add_argument("--backtest",   action="store_true", help="Modo backtest")
    parser.add_argument("--train-only", action="store_true", help="Solo entrenar ML")
    args = parser.parse_args()

    if args.backtest:
        from src.data.backtest import run_backtest
        run_backtest()
    elif args.train_only:
        from src.broker.iqoption_client     import IQOptionClient
        from src.strategies.master_strategy import MasterStrategy
        client   = IQOptionClient()
        client.connect()
        df       = client.get_candles("XAUUSD", 60, 1000)
        strategy = MasterStrategy()
        strategy.train_ml(df)
        logger.info("Entrenamiento completado")
    else:
        from src.bot.trader import Trader
        Trader().start()


if __name__ == "__main__":
    main()
