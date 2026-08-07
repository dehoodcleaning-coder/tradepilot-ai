import requests
import logging
import os
from typing import Dict, Optional, Tuple
from analyst_agent import EvaluationResult
from chart_generator import ChartGenerator
import config

logger = logging.getLogger(__name__)

class MessengerAgent:
    """
    📢 MESSENGER AGENT (INSTITUTIONAL TELEGRAM EDITION)
    Formata e envia os alertas com a mais alta clareza didática e visual no Telegram:
    1. 👀 PRÓ-ALERTA (Aviso Prévio - Não Entrar Ainda)
    2. 🚀 ALERTA OFICIAL DE ENTRADA (Ordem Pronta para Executar)
    3. ❌ SETUP INVALIDADO (Cancelamento do Tópico)
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url_text = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.api_url_photo = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    def format_pre_alert(self, eval_res: EvaluationResult) -> str:
        opp = eval_res.opportunity
        dir_str = "🟢 COMPRA (LONG)" if eval_res.direction == 'BUY' else "🔴 VENDA (SHORT)"
        reasons_txt = "\n".join([f"  • {r}" for r in eval_res.technical_reasons[:2]])
        risks_txt = "\n".join([f"  • {r}" for r in eval_res.risk_factors[:2]]) if eval_res.risk_factors else "  • NENHUM RISCO CRÍTICO IDENTIFICADO."

        msg = (
            f"👀 <b>===================================</b>\n"
            f"⚠️ <b>[HEADS-UP] SETUP SMC EM FORMAÇÃO</b>\n"
            f"👀 <b>===================================</b>\n\n"
            f"🛑 <b>STATUS: AVISO PRÉVIO — NÃO ENTRAR AINDA!</b>\n\n"
            f"📌 <b>Ativo:</b> <code>{opp.symbol}</code>\n"
            f"🧭 <b>Direção Prevista:</b> {dir_str}\n"
            f"📊 <b>Score Parcial:</b> <code>{eval_res.total_score} / 100 PTS</code> ⚠️ (Em Desenvolvimento)\n\n"
            f"🎬 <b>Cenário Peixe Grande:</b>\n<i>{eval_res.setup_scenario}</i>\n\n"
            f"🔎 <b>Zona de Interesse (POI 5m):</b>\n<code>{opp.poi_low:.4f} - {opp.poi_high:.4f}</code>\n"
            f"💵 <b>Preço Atual:</b> <code>{eval_res.entry_price:.4f}</code>\n\n"
            f"💡 <b>Racional Técnico Institucional:</b>\n{reasons_txt}\n\n"
            f"⚠️ <b>Fatores de Atenção:</b>\n{risks_txt}\n\n"
            f"📋 <i>Aguarde a confirmação de entrada neste mesmo tópico do Telegram!</i>"
        )
        return msg

    def format_entry_alert(self, eval_res: EvaluationResult, is_reply: bool = False) -> str:
        opp = eval_res.opportunity
        reply_badge = " ↩️ (CONFIRMAÇÃO DO PRÓ-ALERTA ANTERIOR)" if is_reply else ""

        if eval_res.direction == 'BUY':
            header_banner = (
                f"🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢\n"
                f"🚀 <b>[ALERTA OFICIAL DE ENTRADA - COMPRA (LONG)]</b>{reply_badge}\n"
                f"🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢"
            )
            dir_str = "🟢 COMPRA (LONG)"
        else:
            header_banner = (
                f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                f"💥 <b>[ALERTA OFICIAL DE ENTRADA - VENDA (SHORT)]</b>{reply_badge}\n"
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
            f"⭐ <b>Score do Setup:</b> <b><code>{eval_res.total_score} / 100 PTS</code></b> ✅ (Elegível)\n"
            f"⚖️ <b>Relação Risco:Retorno:</b> <b>1 : {eval_res.rr_ratio} R</b>\n\n"
            f"📥 <b>PREÇO DE ENTRADA:</b> <code>{eval_res.entry_price:.4f}</code>\n"
            f"🛑 <b>STOP LOSS (Invalidação):</b> <code>{eval_res.stop_loss:.4f}</code>\n"
            f"🎯 <b>TAKE PROFIT 1 (2R):</b> <code>{eval_res.take_profit_1:.4f}</code>\n"
            f"🎯 <b>TAKE PROFIT 2 (4R Macro):</b> <code>{eval_res.take_profit_2:.4f}</code>\n\n"
            f"🎬 <b>Cenário SMC Validados:</b>\n<i>{eval_res.setup_scenario}</i>\n\n"
            f"🔎 <b>Racional Técnico Institucional:</b>\n{reasons_txt}\n\n"
            f"🛡 <b>Gestão de Risco & Recomendações:</b>\n"
            f"{risks_txt}\n"
            f"  💡 <i>Regra de Ouro: Ao atingir o TP1 ({eval_res.take_profit_1:.4f}), mova o Stop Loss para o preço de entrada (Break-Even {eval_res.entry_price:.4f})!</i>\n\n"
            f"⏰ <i>{eval_res.timestamp.strftime('%d/%m/%Y %H:%M:%S UTC')} | TradePilot AI v1.0</i>"
        )
        return msg

    def format_invalidation_alert(self, symbol: str, setup_scenario: str, reason: str) -> str:
        msg = (
            f"❌ <b>===================================</b>\n"
            f"🚫 <b>[SETUP INVALIDADO / CANCELADO]</b> ↩️\n"
            f"❌ <b>===================================</b>\n\n"
            f"📌 <b>Ativo:</b> <code>{symbol}</code>\n"
            f"🎬 <b>Cenário:</b> <i>{setup_scenario}</i>\n\n"
            f"⚠️ <b>Motivo do Cancelamento:</b>\n  • {reason}\n\n"
            f"🛑 <b>AÇÃO RECOMENDADA:</b> Desconsiderar qualquer ordem limite associada a este POI. O mercado rompeu a estrutura sem confirmar."
        )
        return msg

    def send_alert(self, eval_res: EvaluationResult, reply_to_message_id: Optional[int] = None) -> Optional[int]:
        if eval_res.alert_type == 'REJECTED':
            return None

        is_reply = reply_to_message_id is not None
        if eval_res.alert_type == 'PRE_ALERT':
            text = self.format_pre_alert(eval_res)
        else:
            text = self.format_entry_alert(eval_res, is_reply=is_reply)

        if not self.bot_token or not self.chat_id:
            print("\n" + "=" * 60)
            print(f"[MOCK TELEGRAM DISPATCH - {eval_res.alert_type} (Reply To: {reply_to_message_id})]:")
            print(text)
            print("=" * 60 + "\n")
            return 999

        # Se a foto estiver HABILITADA no config, tenta enviar foto
        if config.SEND_CHART_IMAGES:
            chart_file = ChartGenerator.generate_signal_chart(eval_res, f"chart_{eval_res.opportunity.symbol.replace('/', '_')}.png")
            if chart_file and os.path.exists(chart_file):
                try:
                    with open(chart_file, 'rb') as photo_file:
                        payload = {
                            "chat_id": self.chat_id,
                            "caption": text,
                            "parse_mode": "HTML"
                        }
                        if reply_to_message_id:
                            payload["reply_to_message_id"] = reply_to_message_id

                        files = {"photo": photo_file}
                        res = requests.post(self.api_url_photo, data=payload, files=files, timeout=15)
                        data = res.json()
                        os.remove(chart_file)

                        if data.get("ok"):
                            sent_msg_id = data["result"]["message_id"]
                            logger.info(f"✨ Alerta + FOTO enviado com SUCESSO via Telegram (Msg #{sent_msg_id})!")
                            return sent_msg_id
                except Exception as e:
                    logger.error(f"Erro ao enviar foto no Telegram: {e}")
                    if os.path.exists(chart_file):
                        os.remove(chart_file)

        # Envio Direto e Instantâneo por MENSAGEM DE TEXTO LIMPA E FORMATADA
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            res = requests.post(self.api_url_text, json=payload, timeout=10)
            data = res.json()
            if data.get("ok"):
                sent_msg_id = data["result"]["message_id"]
                logger.info(f"✨ Alerta TEXTO enviado com SUCESSO via Telegram (Msg #{sent_msg_id})!")
                return sent_msg_id
            else:
                logger.error(f"Erro na API do Telegram sendMessage: {data.get('description')}")
        except Exception as e:
            logger.error(f"Exceção ao enviar mensagem texto Telegram: {e}")
        
        return None

    def send_invalidation(self, symbol: str, setup_scenario: str, reason: str, reply_to_message_id: int) -> bool:
        if not self.bot_token or not self.chat_id:
            return False

        text = self.format_invalidation_alert(symbol, setup_scenario, reason)
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_to_message_id": reply_to_message_id
            }
            res = requests.post(self.api_url_text, json=payload, timeout=10)
            return res.json().get("ok", False)
        except Exception as e:
            logger.error(f"Erro ao enviar invalidação no Telegram: {e}")
            return False
