import requests
import logging
from typing import Dict, Optional
from analyst_agent import EvaluationResult
import config

logger = logging.getLogger(__name__)

class MessengerAgent:
    """
    📢 MESSENGER AGENT (PEIXE GRANDE EDITION)
    Formata alertas elegantes no Telegram com a classificação do Cenário do Vídeo:
    - Cenário 1: Reversão por Captura de Liquidez (Sweep + FVG + POI)
    - Cenário 2: Continuidade de Fluxo Institucional (BOS + OB)
    - Cenário 3: Reação no POI com Confirmação no 1m
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def format_pre_alert(self, eval_res: EvaluationResult) -> str:
        opp = eval_res.opportunity
        dir_str = "🟢 COMPRA (LONG)" if eval_res.direction == 'BUY' else "🔴 VENDA (SHORT)"

        reasons_txt = "\n".join([f"• {r}" for r in eval_res.technical_reasons[:3]])
        risks_txt = "\n".join([f"• {r}" for r in eval_res.risk_factors[:2]])

        msg = (
            f"⚡ <b>[TRADEPILOT AI] - PRÓ-ALERTA (SETUP EM FORMAÇÃO)</b> ⚡\n\n"
            f"🎬 <b>Setup Peixe Grande:</b>\n<code>{eval_res.setup_scenario}</code>\n\n"
            f"📌 <b>Ativo:</b> <code>{opp.symbol}</code> | <b>Direção:</b> {dir_str}\n"
            f"📊 <b>Score Técnico:</b> <code>{eval_res.total_score}/100 pts</code> ⚠️ (Em Desenvolvimento)\n"
            f"⏱ <b>Timeframes:</b> 15m Contexto ➔ 5m POI\n\n"
            f"🔎 <b>Zona de Interesse (POI 5m):</b> <code>{opp.poi_low:.4f} - {opp.poi_high:.4f}</code>\n"
            f"💵 <b>Preço Atual:</b> <code>{eval_res.entry_price:.4f}</code>\n\n"
            f"💡 <b>Racional Técnico:</b>\n{reasons_txt}\n\n"
            f"⚠️ <b>Fatores de Atenção:</b>\n{risks_txt}\n\n"
            f"📋 <i>Aguardando confirmação do gatilho CHoCH no 1m e pontuação >= 80 pts.</i>"
        )
        return msg

    def format_entry_alert(self, eval_res: EvaluationResult) -> str:
        opp = eval_res.opportunity
        if eval_res.direction == 'BUY':
            header = "🚀 <b>[TRADEPILOT AI] - ALERTA OFICIAL DE ENTRADA (LONG)</b> 🚀"
            dir_str = "🟢 COMPRA"
        else:
            header = "💥 <b>[TRADEPILOT AI] - ALERTA OFICIAL DE ENTRADA (SHORT)</b> 💥"
            dir_str = "🔴 VENDA"

        reasons_txt = "\n".join([f"• {r}" for r in eval_res.technical_reasons])
        risks_txt = "\n".join([f"• {r}" for r in eval_res.risk_factors]) if eval_res.risk_factors else "• Nenhum risco crítico identificado."

        msg = (
            f"{header}\n\n"
            f"🎬 <b>Setup Peixe Grande:</b>\n<code>{eval_res.setup_scenario}</code>\n\n"
            f"📌 <b>Ativo:</b> <code>{opp.symbol}</code>\n"
            f"⚡ <b>Direção:</b> {dir_str}\n"
            f"⭐ <b>Score do Setup:</b> <b><code>{eval_res.total_score} / 100 PTS</code></b> ✅\n"
            f"⚖️ <b>Relação Risco:Retorno:</b> <b>1:{eval_res.rr_ratio}</b>\n\n"
            f"📥 <b>Preço de Entrada:</b> <code>{eval_res.entry_price:.4f}</code>\n"
            f"🛑 <b>Stop Loss (Invalidação):</b> <code>{eval_res.stop_loss:.4f}</code>\n"
            f"🎯 <b>Take Profit 1 (2R):</b> <code>{eval_res.take_profit_1:.4f}</code>\n"
            f"🎯 <b>Take Profit 2 (Alvo Macro):</b> <code>{eval_res.take_profit_2:.4f}</code>\n\n"
            f"🔎 <b>Racional Técnico Explicativo:</b>\n{reasons_txt}\n\n"
            f"🛡 <b>Gestão de Risco & Invalidação:</b>\n{risks_txt}\n\n"
            f"⏰ <i>{eval_res.timestamp.strftime('%d/%m/%Y %H:%M:%S UTC')} | TradePilot AI v1.0</i>"
        )
        return msg

    def send_alert(self, eval_res: EvaluationResult) -> bool:
        if eval_res.alert_type == 'REJECTED':
            return False

        if eval_res.alert_type == 'PRE_ALERT':
            text = self.format_pre_alert(eval_res)
        else:
            text = self.format_entry_alert(eval_res)

        if not self.bot_token or not self.chat_id:
            print("\n" + "=" * 60)
            print(f"[MOCK TELEGRAM DISPATCH - {eval_res.alert_type}]:")
            print(text)
            print("=" * 60 + "\n")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            res = requests.post(self.api_url, json=payload, timeout=10)
            data = res.json()
            if data.get("ok"):
                logger.info(f"Alerta {eval_res.alert_type} enviado com sucesso para {eval_res.opportunity.symbol}")
                return True
            else:
                logger.error(f"Erro na API do Telegram: {data.get('description')}")
                return False
        except Exception as e:
            logger.error(f"Exceção ao enviar alerta Telegram: {e}")
            return False
