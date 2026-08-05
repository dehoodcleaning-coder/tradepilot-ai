import ccxt
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BinanceMarketClient:
    """
    Cliente para coleta de dados públicos de mercado com fallback automático de exchanges (Binance, Binance US, Bybit, KuCoin).
    Garante funcionamento independente de restrições de localização/IP.
    """

    def __init__(self):
        # Lista de exchanges suportadas via CCXT como fallback público
        self.exchanges = [
            ("Binance Global", ccxt.binance({'enableRateLimit': True})),
            ("Binance US", ccxt.binanceus({'enableRateLimit': True})),
            ("Bybit", ccxt.bybit({'enableRateLimit': True})),
            ("KuCoin", ccxt.kucoin({'enableRateLimit': True}))
        ]
        self.active_exchange_name = None
        self.active_exchange = None

    def _get_working_exchange(self, symbol: str, timeframe: str):
        if self.active_exchange:
            return self.active_exchange

        for name, exchange in self.exchanges:
            try:
                raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=5)
                if raw:
                    logger.info(f"Conectado com sucesso via {name}")
                    self.active_exchange_name = name
                    self.active_exchange = exchange
                    return exchange
            except Exception as e:
                logger.debug(f"Exchange {name} indisponível nesta região: {e}")
                continue

        # Se nenhum responder com o símbolo original, tenta formato simplificado
        return self.exchanges[0][1]

    def fetch_ohlcv_df(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Busca os dados de velas (OHLCV) com fallback de exchange.
        """
        exchange = self._get_working_exchange(symbol, timeframe)
        try:
            raw_candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw_candles:
                return None

            df = pd.DataFrame(raw_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df
        except Exception as e:
            # Se falhar na exchange atual, tenta resetar a exchange ativa
            self.active_exchange = None
            for name, alt_exchange in self.exchanges:
                try:
                    raw_candles = alt_exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                    if raw_candles:
                        self.active_exchange = alt_exchange
                        self.active_exchange_name = name
                        df = pd.DataFrame(raw_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df[col] = df[col].astype(float)
                        return df
                except Exception:
                    continue

            logger.error(f"Não foi possível buscar OHLCV para {symbol} ({timeframe}): {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Retorna o preço atual do ativo.
        """
        df = self.fetch_ohlcv_df(symbol, timeframe="1m", limit=1)
        if df is not None and not df.empty:
            return float(df['close'].iloc[-1])
        return None
