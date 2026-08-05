import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class POIZone:
    symbol: str
    direction: str  # 'BULLISH' ou 'BEARISH'
    high: float
    low: float
    timeframe: str
    has_fvg: bool
    has_liquidity_sweep: bool
    created_at: pd.Timestamp
    invalidated: bool = False

@dataclass
class Signal:
    symbol: str
    direction: str  # 'BUY' ou 'SELL'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr_ratio: float
    poi_zone: POIZone
    reason: str
    timestamp: pd.Timestamp

class SMCAnalyzer:
    """
    Analisador de Smart Money Concepts (SMC) seguindo a metodologia Peixe Grande Trading.
    Mapeia POIs de Compra/Venda em 5m e confirmações em 1m.
    """

    def __init__(self, buffer_percent: float = 0.0005):
        self.buffer_percent = buffer_percent

    def find_swings(self, df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
        """
        Identifica Topos e Fundos Relevantes (Swing High / Swing Low).
        """
        df = df.copy()
        df['is_swing_high'] = False
        df['is_swing_low'] = False

        highs = df['high'].values
        lows = df['low'].values
        n = len(df)

        for i in range(window, n - window):
            # Swing High
            if all(highs[i] > highs[i - j] for j in range(1, window + 1)) and \
               all(highs[i] > highs[i + j] for j in range(1, window + 1)):
                df.iloc[i, df.columns.get_loc('is_swing_high')] = True

            # Swing Low
            if all(lows[i] < lows[i - j] for j in range(1, window + 1)) and \
               all(lows[i] < lows[i + j] for j in range(1, window + 1)):
                df.iloc[i, df.columns.get_loc('is_swing_low')] = True

        return df

    def detect_fvgs(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Identifica Fair Value Gaps (Inbalança / Desequilíbrio).
        """
        fvgs = []
        n = len(df)
        for i in range(2, n):
            # Bullish FVG: Low do candle atual > High do candle i-2
            if df['low'].iloc[i] > df['high'].iloc[i - 2]:
                fvgs.append({
                    'type': 'BULLISH',
                    'top': df['low'].iloc[i],
                    'bottom': df['high'].iloc[i - 2],
                    'index': i,
                    'datetime': df['datetime'].iloc[i]
                })

            # Bearish FVG: High do candle atual < Low do candle i-2
            elif df['high'].iloc[i] < df['low'].iloc[i - 2]:
                fvgs.append({
                    'type': 'BEARISH',
                    'top': df['low'].iloc[i - 2],
                    'bottom': df['high'].iloc[i],
                    'index': i,
                    'datetime': df['datetime'].iloc[i]
                })
        return fvgs

    def detect_liquidity_sweeps(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """
        Identifica varreduras de liquidez (SSL Sweep / BSL Sweep).
        """
        sweeps = {'ssl_sweeps': [], 'bsl_sweeps': []}
        df_swings = self.find_swings(df)
        
        swing_highs = df_swings[df_swings['is_swing_high']]
        swing_lows = df_swings[df_swings['is_swing_low']]

        for i in range(5, len(df)):
            current_low = df['low'].iloc[i]
            current_high = df['high'].iloc[i]
            current_close = df['close'].iloc[i]

            # SSL Sweep (Varredura de liquidez de venda): Rompe fundo mas fecha acima ou reage
            recent_lows = swing_lows[swing_lows.index < i - 1]['low']
            if not recent_lows.empty:
                last_swing_low = recent_lows.iloc[-1]
                if current_low < last_swing_low and current_close > last_swing_low:
                    sweeps['ssl_sweeps'].append(i)

            # BSL Sweep (Varredura de liquidez de compra): Rompe topo mas fecha abaixo
            recent_highs = swing_highs[swing_highs.index < i - 1]['high']
            if not recent_highs.empty:
                last_swing_high = recent_highs.iloc[-1]
                if current_high > last_swing_high and current_close < last_swing_high:
                    sweeps['bsl_sweeps'].append(i)

        return sweeps

    def identify_5m_pois(self, symbol: str, df_5m: pd.DataFrame) -> List[POIZone]:
        """
        Identifica POIs de Compra e Venda no gráfico macro de 5m.
        """
        df_swings = self.find_swings(df_5m)
        fvgs = self.detect_fvgs(df_5m)
        sweeps = self.detect_liquidity_sweeps(df_5m)
        pois = []

        n = len(df_5m)
        for i in range(10, n - 2):
            # Procura por Order Block de Compra (Último candle de baixa antes de forte impulso de alta)
            is_bullish_impulse = (df_5m['close'].iloc[i+1] > df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] > df_5m['high'].iloc[i])
            
            if df_5m['close'].iloc[i] < df_5m['open'].iloc[i] and is_bullish_impulse:
                ob_low = df_5m['low'].iloc[i]
                ob_high = max(df_5m['high'].iloc[i], df_5m['open'].iloc[i])
                
                # Verifica se há FVG nas proximidades
                has_fvg = any(fvg['type'] == 'BULLISH' and abs(fvg['index'] - i) <= 3 for fvg in fvgs)
                has_sweep = (i in sweeps['ssl_sweeps']) or ((i-1) in sweeps['ssl_sweeps'])

                pois.append(POIZone(
                    symbol=symbol,
                    direction='BULLISH',
                    high=ob_high,
                    low=ob_low,
                    timeframe='5m',
                    has_fvg=has_fvg,
                    has_liquidity_sweep=has_sweep,
                    created_at=df_5m['datetime'].iloc[i]
                ))

            # Procura por Order Block de Venda (Último candle de alta antes de forte impulso de baixa)
            is_bearish_impulse = (df_5m['close'].iloc[i+1] < df_5m['open'].iloc[i+1]) and \
                                 (df_5m['close'].iloc[i+2] < df_5m['low'].iloc[i])
            
            if df_5m['close'].iloc[i] > df_5m['open'].iloc[i] and is_bearish_impulse:
                ob_high = df_5m['high'].iloc[i]
                ob_low = min(df_5m['low'].iloc[i], df_5m['open'].iloc[i])

                has_fvg = any(fvg['type'] == 'BEARISH' and abs(fvg['index'] - i) <= 3 for fvg in fvgs)
                has_sweep = (i in sweeps['bsl_sweeps']) or ((i-1) in sweeps['bsl_sweeps'])

                pois.append(POIZone(
                    symbol=symbol,
                    direction='BEARISH',
                    high=ob_high,
                    low=ob_low,
                    timeframe='5m',
                    has_fvg=has_fvg,
                    has_liquidity_sweep=has_sweep,
                    created_at=df_5m['datetime'].iloc[i]
                ))

        # Retorna apenas os POIs mais recentes ativos
        return pois[-5:] if len(pois) >= 5 else pois

    def analyze_market(self, symbol: str, df_5m: pd.DataFrame, df_1m: pd.DataFrame) -> Optional[Signal]:
        """
        Analisa confluência entre POI 5m e CHoCH 1m para gerar o sinal de entrada.
        """
        if df_5m is None or df_1m is None or len(df_5m) < 20 or len(df_1m) < 20:
            return None

        pois = self.identify_5m_pois(symbol, df_5m)
        if not pois:
            return None

        current_price_1m = df_1m['close'].iloc[-1]
        df_1m_swings = self.find_swings(df_1m)

        for poi in reversed(pois):
            # 🟢 TESTE POI DE COMPRA (BULLISH)
            if poi.direction == 'BULLISH':
                # O preço atual de 1m está tocando ou dentro da zona do POI de 5m (com pequena margem)
                if poi.low * (1 - self.buffer_percent) <= current_price_1m <= poi.high * 1.002:
                    # Verifica CHoCH no 1m (Mudança de caráter: rompe o topo recente no 1m)
                    recent_1m_highs = df_1m_swings[df_1m_swings['is_swing_high']]['high']
                    if not recent_1m_highs.empty:
                        last_1m_high = recent_1m_highs.iloc[-1]
                        
                        # Se o candle recente rompeu o topo do 1m enquanto estava no POI de 5m
                        if df_1m['high'].iloc[-1] > last_1m_high or df_1m['high'].iloc[-2] > last_1m_high:
                            stop_loss = poi.low * (1 - self.buffer_percent)
                            risk = current_price_1m - stop_loss
                            if risk <= 0:
                                continue

                            # Take Profit 1: Topo recente de 5m
                            recent_5m_highs = df_5m['high'].tail(20).max()
                            take_profit_1 = max(recent_5m_highs, current_price_1m + (risk * 2.0))
                            take_profit_2 = current_price_1m + (risk * 4.0)

                            rr_ratio = (take_profit_1 - current_price_1m) / risk

                            return Signal(
                                symbol=symbol,
                                direction='BUY',
                                entry_price=round(current_price_1m, 4),
                                stop_loss=round(stop_loss, 4),
                                take_profit_1=round(take_profit_1, 4),
                                take_profit_2=round(take_profit_2, 4),
                                rr_ratio=round(rr_ratio, 2),
                                poi_zone=poi,
                                reason=f"Mitigação no POI 5m Bullish [{poi.low:.2f} - {poi.high:.2f}] + CHoCH 1m com quebra de topo.",
                                timestamp=pd.Timestamp.now()
                            )

            # 🔴 TESTE POI DE VENDA (BEARISH)
            elif poi.direction == 'BEARISH':
                if poi.low * 0.998 <= current_price_1m <= poi.high * (1 + self.buffer_percent):
                    # Verifica CHoCH no 1m (Mudança de caráter: rompe o fundo recente no 1m)
                    recent_1m_lows = df_1m_swings[df_1m_swings['is_swing_low']]['low']
                    if not recent_1m_lows.empty:
                        last_1m_low = recent_1m_lows.iloc[-1]

                        if df_1m['low'].iloc[-1] < last_1m_low or df_1m['low'].iloc[-2] < last_1m_low:
                            stop_loss = poi.high * (1 + self.buffer_percent)
                            risk = stop_loss - current_price_1m
                            if risk <= 0:
                                continue

                            recent_5m_lows = df_5m['low'].tail(20).min()
                            take_profit_1 = min(recent_5m_lows, current_price_1m - (risk * 2.0))
                            take_profit_2 = current_price_1m - (risk * 4.0)

                            rr_ratio = (current_price_1m - take_profit_1) / risk

                            return Signal(
                                symbol=symbol,
                                direction='SELL',
                                entry_price=round(current_price_1m, 4),
                                stop_loss=round(stop_loss, 4),
                                take_profit_1=round(take_profit_1, 4),
                                take_profit_2=round(take_profit_2, 4),
                                rr_ratio=round(rr_ratio, 2),
                                poi_zone=poi,
                                reason=f"Mitigação no POI 5m Bearish [{poi.low:.2f} - {poi.high:.2f}] + CHoCH 1m com quebra de fundo.",
                                timestamp=pd.Timestamp.now()
                            )

        return None
