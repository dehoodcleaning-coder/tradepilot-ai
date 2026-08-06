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
    alert_type: str        # 'PRE_ALERT' (65-79), 'ENTRY_ELIGIBLE' (80+), 'REJECTED' (<65)
    setup_scenario: str    # 'CENÁRIO 1: Reversão por Captura de Liquidez (Sweep + FVG + POI)', 'CENÁRIO 2: Continuidade de Fluxo (BOS + OB)', etc.
    direction: str         # 'BUY' ou 'SELL'
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
    🧠 ANALYST AGENT (PEIXE GRANDE SMC EDITION)
    Analisa e classifica as oportunidades estritamente de acordo com os cenários
    dos vídeos do Peixe Grande Trading:
    - Cenário 1: Captura de Liquidez (Sweep) + FVG + Mitigação do POI
    - Cenário 2: Continuidade de Fluxo Institucional (BOS + OB + Reteste)
    - Cenário 3: Confirmação Estrita por CHoCH no 1m
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

        # Classificação do Cenário do Vídeo do Peixe Grande
        if opp.has_sweep and opp.has_fvg:
            setup_scenario = "CENÁRIO 1: Reversão por Captura de Liquidez (Sweep + FVG + POI)"
        elif opp.has_fvg:
            setup_scenario = "CENÁRIO 2: Continuidade de Fluxo Institucional (BOS + Order Block)"
        else:
            setup_scenario = "CENÁRIO 3: Reação de POI com Confirmação no 1m"

        # 1. CONTEXTO DE MERCADO (15m) - 15 pts
        trend_15m_up = df_15m['close'].iloc[-1] > df_15m['close'].iloc[-10]
        if (opp.direction == 'BULLISH' and trend_15m_up) or (opp.direction == 'BEARISH' and not trend_15m_up):
            score += 15
            breakdown['Contexto (15m)'] = 15
            reasons.append("Estrutura macro de 15m a favor do fluxo institucional.")
        else:
            score += 5
            breakdown['Contexto (15m)'] = 5
            risks.append("Operação contra a tendência primária de 15m.")

        # 2. MAPEAMENTO DE LIQUIDEZ (SSL / BSL) - 15 pts
        if opp.has_sweep:
            score += 15
            breakdown['Liquidez (Sweep)'] = 15
            reasons.append(f"Captura de Liquidez (Stop Hunt) confirmada no Pivô [{opp.swept_pivot_level:.4f}] antes da entrada.")
        else:
            score += 8
            breakdown['Liquidez (Sweep)'] = 8
            risks.append("Liquidez ainda não varrida (possível indução secundária).")

        # 3. QUALIDADE DO SWEEP (Rejeição de Pavio) - 15 pts
        candle_5m = df_5m.iloc[-1]
        wick_size = abs(candle_5m['high'] - candle_5m['low'])
        body_size = abs(candle_5m['close'] - candle_5m['open'])
        if wick_size > 0 and (body_size / wick_size) < 0.5:
            score += 15
            breakdown['Absorção (Pavio)'] = 15
            reasons.append("Pavio de rejeição expressivo (Absorção das ordens de varejo pelo Peixe Grande).")
        else:
            score += 10
            breakdown['Absorção (Pavio)'] = 10

        # 4. DESLOCAMENTO (Displacement / Impulso) - 15 pts
        vol_5m = df_5m['volume'].tail(5).mean()
        avg_vol = df_5m['volume'].mean()
        if vol_5m > avg_vol * 1.2:
            score += 15
            breakdown['Deslocamento'] = 15
            reasons.append("Deslocamento de preço agressivo com volume institucional elevado.")
        else:
            score += 10
            breakdown['Deslocamento'] = 10

        # 5. POI & FAIR VALUE GAP (FVG) - 10 pts
        if opp.has_fvg:
            score += 10
            breakdown['POI & FVG'] = 10
            reasons.append("Order Block (OB) validado com Ineficiência / Fair Value Gap (FVG).")
        else:
            score += 5
            breakdown['POI & FVG'] = 5
            risks.append("Order Block sem ineficiência (FVG) evidente.")

        # 6. GATILHO CHoCH (1m) - 15 pts
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
            reasons.append("Gatilho CHoCH (Mudança de Caráter) confirmado no gráfico de 1m.")
        else:
            score += 5
            breakdown['CHoCH (1m)'] = 5
            risks.append("CHoCH de 1m ainda em formação (entrada por mitigação direta).")

        # 7. RISCO / RETORNO (Mínimo 3R) - 15 pts
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
            reasons.append(f"Excelente Relação Risco:Retorno (1:{rr_ratio:.2f} >= 1:3.0).")
        elif rr_ratio >= 2.0:
            score += 10
            breakdown['Risco/Retorno'] = 10
        else:
            score += 5
            breakdown['Risco/Retorno'] = 5
            risks.append("Relação R:R abaixo de 1:3.")

        # Classificação do Tipo de Alerta
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
            setup_scenario=setup_scenario,
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
