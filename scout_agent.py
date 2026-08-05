import logging
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from binance_client import BinanceMarketClient
import config

logger = logging.getLogger(__name__)

@dataclass
class ScoutOpportunity:
    symbol: str
    direction: str  # 'BULLISH' ou 'BEARISH'
    df_15m: pd.DataFrame
    df_5m: pd.DataFrame
    df_1m: pd.DataFrame
    current_price: float
    poi_high: float
    poi_low: float
    has_fvg: bool
    has_sweep: bool
    timestamp: pd.Timestamp

class ScoutAgent:
    """
    🕵️ SCOUT AGENT
    Monitora os mercados 24/7, analisa a estrutura de 15m e 5m, e identifica
    oportunidades brutas em desenvolvimento para repassar ao Analyst Agent.
    """

    def __init__(self, client: BinanceMarketClient):
        self.client = client

    def find_swings(self, df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
        df = df.copy()
        df['is_swing_high'] = False
        df['is_swing_low'] = False

        highs = df['high'].values
        lows = df['low'].values
        n = len(df)

        for i in range(window, n - window):
            if all(highs[i] > highs[i - j] for j in range(1, window + 1)) and \
               all(highs[i] > highs[i + j] for j in range(1, window + 1)):
                df.iloc[i, df.columns.get_loc('is_swing_high')] = True

            if all(lows[i] < lows[i - j] for j in range(1, window + 1)) and \
               all(lows[i] < lows[i + j] for j in range(1, window + 1)):
                df.iloc[i, df.columns.get_loc('is_swing_low')] = True

        return df

    def scan_symbol(self, symbol: str) -> Optional[ScoutOpportunity]:
        """
        Escaneia um símbolo específico buscando formações de POI e Liquidez.
        """
        df_15m = self.client.fetch_ohlcv_df(symbol, timeframe=config.CONTEXT_TIMEFRAME, limit=100)
        df_5m = self.client.fetch_ohlcv_df(symbol, timeframe=config.STRUCTURE_TIMEFRAME, limit=100)
        df_1m = self.client.fetch_ohlcv_df(symbol, timeframe=config.TRIGGER_TIMEFRAME, limit=100)

        if df_15m is None or df_5m is None or df_1m is None:
            return None

        if len(df_15m) < 20 or len(df_5m) < 20 or len(df_1m) < 20:
            return None

        current_price = df_1m['close'].iloc[-1]
        df_5m_swings = self.find_swings(df_5m)

        # Procura por Order Blocks e FVGs relevantes no 5m
        n_5m = len(df_5m)
        for i in range(n_5m - 15, n_5m - 2):
            # Bullish POI Candidate
            is_bullish_impulse = (df_5m['close'].iloc[i+1] > df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] > df_5m['high'].iloc[i])
            
            if df_5m['close'].iloc[i] < df_5m['open'].iloc[i] and is_bullish_impulse:
                ob_low = df_5m['low'].iloc[i]
                ob_high = max(df_5m['high'].iloc[i], df_5m['open'].iloc[i])

                # Se o preço atual está próximo da zona (dentro ou aproximando do POI)
                if ob_low * 0.998 <= current_price <= ob_high * 1.003:
                    has_fvg = df_5m['low'].iloc[i+2] > df_5m['high'].iloc[i]
                    has_sweep = df_5m['low'].iloc[i] < df_5m_swings['low'].tail(20).min()

                    return ScoutOpportunity(
                        symbol=symbol,
                        direction='BULLISH',
                        df_15m=df_15m,
                        df_5m=df_5m,
                        df_1m=df_1m,
                        current_price=current_price,
                        poi_high=ob_high,
                        poi_low=ob_low,
                        has_fvg=has_fvg,
                        has_sweep=has_sweep,
                        timestamp=pd.Timestamp.now()
                    )

            # Bearish POI Candidate
            is_bearish_impulse = (df_5m['close'].iloc[i+1] < df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] < df_5m['low'].iloc[i])

            if df_5m['close'].iloc[i] > df_5m['open'].iloc[i] and is_bearish_impulse:
                ob_high = df_5m['high'].iloc[i]
                ob_low = min(df_5m['low'].iloc[i], df_5m['open'].iloc[i])

                if ob_low * 0.997 <= current_price <= ob_high * 1.002:
                    has_fvg = df_5m['high'].iloc[i+2] < df_5m['low'].iloc[i]
                    has_sweep = df_5m['high'].iloc[i] > df_5m_swings['high'].tail(20).max()

                    return ScoutOpportunity(
                        symbol=symbol,
                        direction='BEARISH',
                        df_15m=df_15m,
                        df_5m=df_5m,
                        df_1m=df_1m,
                        current_price=current_price,
                        poi_high=ob_high,
                        poi_low=ob_low,
                        has_fvg=has_fvg,
                        has_sweep=has_sweep,
                        timestamp=pd.Timestamp.now()
                    )

        return None
