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
    setup_scenario: str    # 'CENÁRIO 1: Reversão por Captura de Liquidez (Sweep + FVG + POI)', etc.
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
    🧠 ANALYST AGENT (PEIXE GRANDE RSI DIVERGENCE EDITION)
    Integra a validação da Divergência Institucional no RSI(14) (Escadinha de Exaustão):
    - Confirma se o rompimento do pivô foi um falso rompimento para captura de liquidez (Sweep).
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

        # 2. CAPTURA DE LIQUIDEZ (SWEEP DO PIVÔ) - 20 pts
        if opp.has_sweep:
            score += 20
            breakdown['Liquidez (Sweep)'] = 20
            if opp.swept_pivot_level > 0:
                reasons.append(f"Captura de Liquidez (Stop Hunt) confirmada no Pivô [{opp.swept_pivot_level:.4f}] antes da entrada.")
            else:
                reasons.append("Captura de Liquidez (Stop Hunt da estrutura recente) confirmada antes da entrada.")
        else:
            score += 0
            breakdown['Liquidez (Sweep)'] = 0
            risks.append("CRÍTICO: Liquidez ainda não varrida (alto risco de stop por indução).")

        # 3. DIVERGÊNCIA DE RSI (14) - 15 pts (NOVO MÓDULO PEIXE GRANDE)
        if opp.has_rsi_divergence:
            score += 15
            breakdown['Divergência RSI(14)'] = 15
            reasons.append("Divergência no RSI(14) confirmada! (Preço renovou pivô mas RSI fez escada de exaustão).")
        else:
            score += 5
            breakdown['Divergência RSI(14)'] = 5
            risks.append("Sem divergência nítida de RSI(14) no rompimento do pivô.")

        # 4. QUALIDADE DO SWEEP (Rejeição de Pavio) - 15 pts
        candle_5m = df_5m.iloc[-1]
        wick_size = abs(candle_5m['high'] - candle_5m['low'])
        body_size = abs(candle_5m['close'] - candle_5m['open'])
        if wick_size > 0 and (body_size / wick_size) < 0.5:
            score += 15
            breakdown['Absorção (Pavio)'] = 15
            reasons.append("Pavio de rejeição expressivo (Absorção das ordens pelo Peixe Grande).")
        else:
            score += 10
            breakdown['Absorção (Pavio)'] = 10

        # 5. POI & FAIR VALUE GAP (FVG) - 10 pts
        if opp.has_fvg:
            score += 10
            breakdown['POI & FVG'] = 10
            reasons.append("Order Block (OB) validado com Ineficiência / Fair Value Gap (FVG).")
        else:
            score += 0
            breakdown['POI & FVG'] = 0
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
            risks.append("CHoCH de 1m ainda em formação.")

        # 7. RISCO / RETORNO (Mínimo 3R) - 10 pts
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
            score += 10
            breakdown['Risco/Retorno'] = 10
            reasons.append(f"Excelente Relação Risco:Retorno (1:{rr_ratio:.2f} >= 1:3.0).")
        else:
            score += 5
            breakdown['Risco/Retorno'] = 5

        # REGRA RIGOROSA PEIXE GRANDE:
        # Para ser ENTRY_ELIGIBLE (Score >= 80), É OBRIGATÓRIO TER SWEEP DA LIQUIDEZ DO PIVÔ!
        if score >= config.ENTRY_ALERT_MIN_SCORE and opp.has_sweep:
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
