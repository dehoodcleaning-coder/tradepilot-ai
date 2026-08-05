import logging
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from scout_agent import ScoutOpportunity
import config

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    opportunity: ScoutOpportunity
    total_score: int
    score_breakdown: Dict[str, int]
    alert_type: str  # 'PRE_ALERT' (65-79), 'ENTRY_ELIGIBLE' (80+), 'REJECTED' (<65)
    direction: str   # 'BUY' ou 'SELL'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr_ratio: float
    technical_reasons: List[str]
    risk_factors: List[str]
    timestamp: pd.Timestamp

class AnalystAgent:
    """
    🧠 ANALYST AGENT
    Aplica o modelo rigoroso de pontuação de 100 pontos no TradePilot AI:
    - Contexto (15m): 15 pts
    - Mapeamento de Liquidez: 15 pts
    - Qualidade do Sweep: 15 pts
    - Deslocamento (Displacement): 15 pts
    - Mudança de Estrutura (MSS/CHoCH 1m): 15 pts
    - POI & FVG: 10 pts
    - Relação Risco/Retorno (R:R >= 3:1): 15 pts
    """

    def __init__(self, buffer_percent: float = 0.0005):
        self.buffer_percent = buffer_percent

    def evaluate_opportunity(self, opp: ScoutOpportunity) -> EvaluationResult:
        score = 0
        breakdown = {}
        reasons = []
        risks = []

        df_15m = opp.df_15m
        df_5m = opp.df_5m
        df_1m = opp.df_1m
        cp = opp.current_price

        # 1. CONTEXTO DE MERCADO (15m) - 15 pts
        trend_15m_up = df_15m['close'].iloc[-1] > df_15m['close'].iloc[-10]
        if (opp.direction == 'BULLISH' and trend_15m_up) or (opp.direction == 'BEARISH' and not trend_15m_up):
            score += 15
            breakdown['Contexto (15m)'] = 15
            reasons.append("Estrutura macro de 15m alinhada com a direção da operação.")
        else:
            score += 5
            breakdown['Contexto (15m)'] = 5
            risks.append("Operação contra a tendência primária de 15m.")

        # 2. MAPEAMENTO DE LIQUIDED (BSL / SSL) - 15 pts
        if opp.has_sweep:
            score += 15
            breakdown['Liquidez'] = 15
            reasons.append("Pool de liquidez relevante varrido antes do toque no POI.")
        else:
            score += 8
            breakdown['Liquidez'] = 8
            risks.append("Liquidez ainda não varrida completamente.")

        # 3. QUALIDADE DO SWEEP (Rejeição de Pavio) - 15 pts
        candle_5m = df_5m.iloc[-1]
        wick_size = abs(candle_5m['high'] - candle_5m['low'])
        body_size = abs(candle_5m['close'] - candle_5m['open'])
        if wick_size > 0 and (body_size / wick_size) < 0.5:
            score += 15
            breakdown['Sweep Quality'] = 15
            reasons.append("Forte pavio de rejeição demonstrando absorção institucional.")
        else:
            score += 10
            breakdown['Sweep Quality'] = 10

        # 4. DESLOCAMENTO (Displacement) - 15 pts
        vol_5m = df_5m['volume'].tail(5).mean()
        avg_vol = df_5m['volume'].mean()
        if vol_5m > avg_vol * 1.2:
            score += 15
            breakdown['Deslocamento'] = 15
            reasons.append("Deslocamento com volume acima da média institucional.")
        else:
            score += 10
            breakdown['Deslocamento'] = 10

        # 5. POI & FAIR VALUE GAP (FVG) - 10 pts
        if opp.has_fvg:
            score += 10
            breakdown['POI & FVG'] = 10
            reasons.append("Order Block validado com Fair Value Gap (FVG) não mitigado.")
        else:
            score += 5
            breakdown['POI & FVG'] = 5
            risks.append("Order Block sem desequilíbrio (FVG) evidente.")

        # 6. MUDANÇA DE ESTRUTURA (MSS / CHoCH 1m) & ESTRUTURA - 15 pts
        # Verifica se no 1m houve rompimento da última máxima/mínima
        recent_1m_high = df_1m['high'].tail(10).max()
        recent_1m_low = df_1m['low'].tail(10).min()
        
        has_choch = False
        if opp.direction == 'BULLISH' and df_1m['high'].iloc[-1] >= recent_1m_high * 0.9995:
            has_choch = True
        elif opp.direction == 'BEARISH' and df_1m['low'].iloc[-1] <= recent_1m_low * 1.0005:
            has_choch = True

        if has_choch:
            score += 15
            breakdown['CHoCH (1m)'] = 15
            reasons.append("CHoCH (Mudança de Caráter) confirmado no gráfico de 1m.")
        else:
            score += 5
            breakdown['CHoCH (1m)'] = 5
            risks.append("Gatilho de CHoCH no 1m ainda em desenvolvimento.")

        # 7. CÁLCULO DE RISCO / RETORNO (R:R >= 3.0) - 15 pts
        direction = 'BUY' if opp.direction == 'BULLISH' else 'SELL'
        if direction == 'BUY':
            stop_loss = opp.poi_low * (1 - self.buffer_percent)
            risk = cp - stop_loss
            if risk <= 0:
                risk = cp * 0.002
                stop_loss = cp - risk
            take_profit_1 = cp + (risk * 2.0)
            take_profit_2 = cp + (risk * 4.0)
            rr_ratio = (take_profit_2 - cp) / risk
        else:
            stop_loss = opp.poi_high * (1 + self.buffer_percent)
            risk = stop_loss - cp
            if risk <= 0:
                risk = cp * 0.002
                stop_loss = cp + risk
            take_profit_1 = cp - (risk * 2.0)
            take_profit_2 = cp - (risk * 4.0)
            rr_ratio = (cp - take_profit_2) / risk

        if rr_ratio >= config.MIN_RISK_REWARD:
            score += 15
            breakdown['Risco/Retorno'] = 15
            reasons.append(f"Relação Risco:Retorno excelente (1:{rr_ratio:.2f} >= 1:3.0).")
        elif rr_ratio >= 2.0:
            score += 10
            breakdown['Risco/Retorno'] = 10
        else:
            score += 5
            breakdown['Risco/Retorno'] = 5
            risks.append("Relação R:R abaixo de 1:3.")

        # DETERMINA O TIPO DE ALERTA BASEADO NO SCORE
        if score >= config.ENTRY_ALERT_MIN_SCORE:
            alert_type = 'ENTRY_ELIGIBLE'
        elif score >= config.PRE_ALERT_MIN_SCORE:
            alert_type = 'PRE_ALERT'
        else:
            alert_type = 'REJECTED'

        return EvaluationResult(
            opportunity=opp,
            total_score=score,
            score_breakdown=breakdown,
            alert_type=alert_type,
            direction=direction,
            entry_price=round(cp, 4),
            stop_loss=round(stop_loss, 4),
            take_profit_1=round(take_profit_1, 4),
            take_profit_2=round(take_profit_2, 4),
            rr_ratio=round(rr_ratio, 2),
            technical_reasons=reasons,
            risk_factors=risks,
            timestamp=pd.Timestamp.now()
        )
