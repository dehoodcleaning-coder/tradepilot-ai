import requests
import logging
import os
from typing import Dict, Optional
from analyst_agent import EvaluationResult
from chart_generator import ChartGenerator
import config

logger = logging.getLogger(__name__)

class MessengerAgent:
    """
    📢 MESSENGER AGENT (VISUAL PRO EDITION)
    Diferencia visualmente e de forma INCONFUNDÍVEL os dois tipos de notificação:
    1. 👀 PRÓ-ALERTA (Apenas Aviso de Setup em Formação - NÃO ENTRAR)
    2. 🚀 ALERTA OFICIAL DE ENTRADA (Ordem Pronta para Executar)
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url_text = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.api_url_photo = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    def format_pre_alert(self, eval_res: EvaluationResult) -> str:
        """
        👀 PRÓ-ALERTA: Formato Compacto Amarelo/Laranja (Apenas Observação)
        """
        opp = eval_res.opportunity
        dir_str = "🟢 COMPRA (LONG)" if eval_res.direction == 'BUY' else "🔴 VENDA (SHORT)"
        reasons_txt = "\n".join([f"  • {r}" for r in eval_res.technical_reasons[:2]])

        msg = (
            f"👀 <b>===================================</b>\n"
            f"⚠️ <b>[HEADS-UP] PRÓ-ALERTA: SETUP EM FORMAÇÃO</b>\n"
            f"👀 <b>===================================</b>\n\n"
            f"🛑 <b>NÃO ENTRAR AINDA! ESTE É APENAS UM AVISO PRÉVIO.</b>\n\n"
            f"📌 <b>Ativo:</b> <code>{opp.symbol}</code> | <b>Sentido:</b> {dir_str}\n"
            f"📊 <b>Score Parcial:</b> <code>{eval_res.total_score} / 100 pts</code> (Status: Em Teste)\n"
            f"🎬 <b>Cenário:</b> <i>{eval_res.setup_scenario}</i>\n\n"
            f"🔎 <b>Faixa do POI (5m):</b> <code>{opp.poi_low:.4f} - {opp.poi_high:.4f}</code>\n"
            f"💵 <b>Preço Atual:</b> <code>{eval_res.entry_price:.4f}</code>\n\n"
            f"💡 <b>Observações:</b>\n{reasons_txt}\n\n"
            f"⏳ <i>Aguarde a confirmação de entrada e o disparo do Alerta Oficial!</i>"
        )
        return msg

    def format_entry_alert(self, eval_res: EvaluationResult) -> str:
        """
        🚀 ALERTA OFICIAL DE ENTRADA: Formato Completo e Destacado (Pronto para Execução)
        """
        opp = eval_res.opportunity
        if eval_res.direction == 'BUY':
            header_banner = (
                f"🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢\n"
                f"🚀 <b>[ALERTA OFICIAL DE ENTRADA - COMPRA (LONG)]</b>\n"
                f"🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢"
            )
            dir_str = "🟢 COMPRA (LONG)"
        else:
            header_banner = (
                f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                f"💥 <b>[ALERTA OFICIAL DE ENTRADA - VENDA (SHORT)]</b>\n"
                f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴"
            )
            dir_str = "🔴 VENDA (SHORT)"

        reasons_txt = "\n".join([f"  ✅ {r}" for r in eval_res.technical_reasons])
        risks_txt = "\n".join([f"  ⚠️ {r}" for r in eval_res.risk_factors]) if eval_res.risk_factors else "  ✅ Risco controlado dentro dos padrões."

        msg = (
            f"{header_banner}\n\n"
            f"⚡ <b>EXECUTAR ORDEM AGORA NO MERCADO!</b> ⚡\n\n"
            f"📌 <b>Ativo:</b> <code>{opp.symbol}</code>\n"
            f"🧭 <b>Direção:</b> <b>{dir_str}</b>\n"
            f"⭐ <b>Score do Setup:</b> <b><code>{eval_res.total_score} / 100 PTS</code></b> (Elegível)\n"
            f"⚖️ <b>Risco:Retorno:</b> <b>1 : {eval_res.rr_ratio}</b>\n\n"
            f"📥 <b>PREÇO DE ENTRADA:</b> <code>{eval_res.entry_price:.4f}</code>\n"
            f"🛑 <b>STOP LOSS (Invalidação):</b> <code>{eval_res.stop_loss:.4f}</code>\n"
            f"🎯 <b>TAKE PROFIT 1 (2R):</b> <code>{eval_res.take_profit_1:.4f}</code>\n"
            f"🎯 <b>TAKE PROFIT 2 (4R Macro):</b> <code>{eval_res.take_profit_2:.4f}</code>\n\n"
            f"🎬 <b>Cenário SMC Validados:</b>\n<i>{eval_res.setup_scenario}</i>\n\n"
            f"🔎 <b>Racional Técnico Institucional:</b>\n{reasons_txt}\n\n"
            f"🛡 <b>Gestão de Risco & Recomendações:</b>\n"
            f"{risks_txt}\n"
            f"  💡 <i>Dica: Ao atingir o TP1 (2R), mova o Stop Loss para o preço de entrada (Break-Even)!</i>\n\n"
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

        # Gera o Gráfico Visual
        chart_file = ChartGenerator.generate_signal_chart(eval_res, f"chart_{eval_res.opportunity.symbol.replace('/', '_')}.png")

        if not self.bot_token or not self.chat_id:
            print("\n" + "=" * 60)
            print(f"[MOCK TELEGRAM DISPATCH - {eval_res.alert_type}]:")
            print(text)
            print("=" * 60 + "\n")
            if chart_file and os.path.exists(chart_file):
                os.remove(chart_file)
            return False

        # Tenta enviar como FOTO com legenda
        if chart_file and os.path.exists(chart_file):
            try:
                with open(chart_file, 'rb') as photo_file:
                    payload = {
                        "chat_id": self.chat_id,
                        "caption": text,
                        "parse_mode": "HTML"
                    }
                    files = {"photo": photo_file}
                    res = requests.post(self.api_url_photo, data=payload, files=files, timeout=15)
                    data = res.json()
                    
                    os.remove(chart_file) # Remove arquivo temporário

                    if data.get("ok"):
                        logger.info(f"✨ Alerta {eval_res.alert_type} + GRÁFICO enviado com SUCESSO via Telegram!")
                        return True
                    else:
                        logger.warning(f"Falha sendPhoto ({data.get('description')}). Enviando apenas texto...")
            except Exception as e:
                logger.error(f"Erro ao enviar foto no Telegram: {e}")
                if os.path.exists(chart_file):
                    os.remove(chart_file)

        # Fallback: Envia como mensagem de texto normal
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            res = requests.post(self.api_url_text, json=payload, timeout=10)
            return res.json().get("ok", False)
        except Exception as e:
            logger.error(f"Exceção ao enviar mensagem texto Telegram: {e}")
            return False
