import logging
import pandas as pd
import numpy as np
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
    has_rsi_divergence: bool
    timestamp: pd.Timestamp

class ScoutAgent:
    """
    🕵️ SCOUT AGENT (RSI DIVERGENCE & SMC POI ENGINE)
    Identifica os Pivôs de Alta e Baixa, detecta o rompimento/varredura de liquidez (Sweep)
    e confirma se o indicador RSI(14) gerou a DIVERGÊNCIA INSTITUCIONAL (Escadinha de Exaustão).
    """

    def __init__(self, client: BinanceMarketClient):
        self.client = client

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

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
        
        # Calcula RSI de 14 períodos no 5m
        df_5m['rsi'] = self.calculate_rsi(df_5m, 14)
        df_5m_swings = self.find_swings(df_5m)

        swing_highs = df_5m_swings[df_5m_swings['is_swing_high']]
        swing_lows = df_5m_swings[df_5m_swings['is_swing_low']]

        n_5m = len(df_5m)
        for i in range(n_5m - 15, n_5m - 2):
            # 🟢 BULLISH POI (Origem da varredura de fundo / SSL Sweep + Divergência de RSI)
            is_bullish_impulse = (df_5m['close'].iloc[i+1] > df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] > df_5m['high'].iloc[i])
            
            if df_5m['close'].iloc[i] < df_5m['open'].iloc[i] and is_bullish_impulse:
                ob_low = df_5m['low'].iloc[i]
                ob_high = max(df_5m['high'].iloc[i], df_5m['open'].iloc[i])

                if ob_low * 0.998 <= current_price <= ob_high * 1.003:
                    has_fvg = df_5m['low'].iloc[i+2] > df_5m['high'].iloc[i]
                    
                    past_lows = swing_lows[swing_lows.index < i]
                    has_sweep = False
                    has_rsi_div = False
                    swept_level = 0.0
                    
                    if not past_lows.empty:
                        last_pivot_idx = past_lows.index[-1]
                        last_pivot_low = past_lows.loc[last_pivot_idx, 'low']
                        last_pivot_rsi = past_lows.loc[last_pivot_idx, 'rsi']

                        current_low = min(df_5m['low'].iloc[i], df_5m['low'].iloc[i-1])
                        current_rsi = df_5m['rsi'].iloc[i]

                        # Sweep: Preço fez fundo mais baixo ou rompeu o pivô
                        if current_low <= last_pivot_low * 1.0005:
                            has_sweep = True
                            swept_level = float(last_pivot_low)
                            # Divergência de RSI de Alta: Preço faz fundo mais baixo, mas RSI faz fundo mais alto!
                            if pd.notna(current_rsi) and pd.notna(last_pivot_rsi) and current_rsi > last_pivot_rsi:
                                has_rsi_div = True

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
                        has_rsi_divergence=has_rsi_div,
                        timestamp=pd.Timestamp.now()
                    )

            # 🔴 BEARISH POI (Origem da varredura de topo / BSL Sweep + Divergência de RSI)
            is_bearish_impulse = (df_5m['close'].iloc[i+1] < df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] < df_5m['low'].iloc[i])

            if df_5m['close'].iloc[i] > df_5m['open'].iloc[i] and is_bearish_impulse:
                ob_high = df_5m['high'].iloc[i]
                ob_low = min(df_5m['low'].iloc[i], df_5m['open'].iloc[i])

                if ob_low * 0.997 <= current_price <= ob_high * 1.002:
                    has_fvg = df_5m['high'].iloc[i+2] < df_5m['low'].iloc[i]
                    
                    past_highs = swing_highs[swing_highs.index < i]
                    has_sweep = False
                    has_rsi_div = False
                    swept_level = 0.0

                    if not past_highs.empty:
                        last_pivot_idx = past_highs.index[-1]
                        last_pivot_high = past_highs.loc[last_pivot_idx, 'high']
                        last_pivot_rsi = past_highs.loc[last_pivot_idx, 'rsi']

                        current_high = max(df_5m['high'].iloc[i], df_5m['high'].iloc[i-1])
                        current_rsi = df_5m['rsi'].iloc[i]

                        # Sweep: Preço fez topo mais alto ou rompeu o pivô
                        if current_high >= last_pivot_high * 0.9995:
                            has_sweep = True
                            swept_level = float(last_pivot_high)
                            # Divergência de RSI de Baixa: Preço faz topo mais alto, mas RSI faz topo mais baixo!
                            if pd.notna(current_rsi) and pd.notna(last_pivot_rsi) and current_rsi < last_pivot_rsi:
                                has_rsi_div = True

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
                        has_rsi_divergence=has_rsi_div,
                        timestamp=pd.Timestamp.now()
                    )

        return None
