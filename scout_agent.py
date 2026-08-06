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
    swept_pivot_level: float
    has_fvg: bool
    has_sweep: bool
    timestamp: pd.Timestamp

class ScoutAgent:
    """
    🕵️ SCOUT AGENT (PEIXE GRANDE PIVOT & POI ENGINE)
    Identifica com máxima precisão os Pivôs de Alta e Pivôs de Baixa (Topos e Fundos Relevantes),
    verifica a varredura da liquidez desse pivô (Sweep) e mapeia o POI de origem.
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
        df_15m = self.client.fetch_ohlcv_df(symbol, timeframe=config.CONTEXT_TIMEFRAME, limit=100)
        df_5m = self.client.fetch_ohlcv_df(symbol, timeframe=config.STRUCTURE_TIMEFRAME, limit=100)
        df_1m = self.client.fetch_ohlcv_df(symbol, timeframe=config.TRIGGER_TIMEFRAME, limit=100)

        if df_15m is None or df_5m is None or df_1m is None:
            return None

        if len(df_15m) < 20 or len(df_5m) < 20 or len(df_1m) < 20:
            return None

        current_price = df_1m['close'].iloc[-1]
        df_5m_swings = self.find_swings(df_5m)

        swing_highs = df_5m_swings[df_5m_swings['is_swing_high']]
        swing_lows = df_5m_swings[df_5m_swings['is_swing_low']]

        n_5m = len(df_5m)
        for i in range(n_5m - 15, n_5m - 2):
            # 🟢 BULLISH POI (Origem da varredura de fundo / SSL Sweep)
            is_bullish_impulse = (df_5m['close'].iloc[i+1] > df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] > df_5m['high'].iloc[i])
            
            if df_5m['close'].iloc[i] < df_5m['open'].iloc[i] and is_bullish_impulse:
                ob_low = df_5m['low'].iloc[i]
                ob_high = max(df_5m['high'].iloc[i], df_5m['open'].iloc[i])

                if ob_low * 0.998 <= current_price <= ob_high * 1.003:
                    has_fvg = df_5m['low'].iloc[i+2] > df_5m['high'].iloc[i]
                    
                    # Verifica se a mínima deste candle ou do anterior varreu um Pivô de Baixa anterior
                    past_lows = swing_lows[swing_lows.index < i]['low']
                    has_sweep = False
                    swept_level = 0.0
                    if not past_lows.empty:
                        last_pivot_low = past_lows.iloc[-1]
                        if df_5m['low'].iloc[i] <= last_pivot_low or df_5m['low'].iloc[i-1] <= last_pivot_low:
                            has_sweep = True
                            swept_level = float(last_pivot_low)

                    return ScoutOpportunity(
                        symbol=symbol,
                        direction='BULLISH',
                        df_15m=df_15m,
                        df_5m=df_5m,
                        df_1m=df_1m,
                        current_price=current_price,
                        poi_high=ob_high,
                        poi_low=ob_low,
                        swept_pivot_level=swept_level,
                        has_fvg=has_fvg,
                        has_sweep=has_sweep,
                        timestamp=pd.Timestamp.now()
                    )

            # 🔴 BEARISH POI (Origem da varredura de topo / BSL Sweep)
            is_bearish_impulse = (df_5m['close'].iloc[i+1] < df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] < df_5m['low'].iloc[i])

            if df_5m['close'].iloc[i] > df_5m['open'].iloc[i] and is_bearish_impulse:
                ob_high = df_5m['high'].iloc[i]
                ob_low = min(df_5m['low'].iloc[i], df_5m['open'].iloc[i])

                if ob_low * 0.997 <= current_price <= ob_high * 1.002:
                    has_fvg = df_5m['high'].iloc[i+2] < df_5m['low'].iloc[i]
                    
                    # Verifica se a máxima deste candle ou do anterior varreu um Pivô de Alta anterior
                    past_highs = swing_highs[swing_highs.index < i]['high']
                    has_sweep = False
                    swept_level = 0.0
                    if not past_highs.empty:
                        last_pivot_high = past_highs.iloc[-1]
                        if df_5m['high'].iloc[i] >= last_pivot_high or df_5m['high'].iloc[i-1] >= last_pivot_high:
                            has_sweep = True
                            swept_level = float(last_pivot_high)

                    return ScoutOpportunity(
                        symbol=symbol,
                        direction='BEARISH',
                        df_15m=df_15m,
                        df_5m=df_5m,
                        df_1m=df_1m,
                        current_price=current_price,
                        poi_high=ob_high,
                        poi_low=ob_low,
                        swept_pivot_level=swept_level,
                        has_fvg=has_fvg,
                        has_sweep=has_sweep,
                        timestamp=pd.Timestamp.now()
                    )

        return None
