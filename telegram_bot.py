import requests
import logging
from typing import Optional
from smc_analyzer import Signal

logger = logging.getLogger(__name__)

class TelegramSignalNotifier:
    """
    Notificador via Telegram API para envio de alertas de trading.
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def format_signal_message(self, signal: Signal) -> str:
        """
        Formata o sinal em HTML elegante para o Telegram.
        """
        if signal.direction == 'BUY':
            header = f"🟩 <b>SINAL PEIXE GRANDE - POI DE COMPRA (LONG)</b> 🟩"
            dir_emoji = "🟢 COMPRA"
        else:
            header = f"🟥 <b>SINAL PEIXE GRANDE - POI DE VENDA (SHORT)</b> 🟥"
            dir_emoji = "🔴 VENDA"

        fvg_status = "Sim ✅" if signal.poi_zone.has_fvg else "Não ❌"
        sweep_status = "Sim ✅" if signal.poi_zone.has_liquidity_sweep else "Não ❌"

        message = (
            f"{header}\n\n"
            f"📌 <b>Ativo:</b> <code>{signal.symbol}</code>\n"
            f"⚡ <b>Direção:</b> {dir_emoji}\n"
            f"⏱ <b>Timeframes:</b> POI 5m + Confirmação CHoCH 1m\n\n"
            f"📥 <b>Preço de Entrada:</b> <code>{signal.entry_price:.4f}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{signal.stop_loss:.4f}</code>\n"
            f"🎯 <b>Take Profit 1:</b> <code>{signal.take_profit_1:.4f}</code>\n"
            f"🎯 <b>Take Profit 2:</b> <code>{signal.take_profit_2:.4f}</code>\n"
            f"⚖️ <b>Relação R:R:</b> 1:{signal.rr_ratio}\n\n"
            f"🔎 <b>Validação do POI 5m:</b>\n"
            f"• Faixa do POI: <code>{signal.poi_zone.low:.4f} - {signal.poi_zone.high:.4f}</code>\n"
            f"• FVG Presente: {fvg_status}\n"
            f"• Liquidez Varrida (Sweep): {sweep_status}\n"
            f"💡 <b>Motivo:</b> {signal.reason}\n\n"
            f"⏰ <i>{signal.timestamp.strftime('%d/%m/%Y %H:%M:%S UTC')}</i>"
        )
        return message

    def send_signal(self, signal: Signal) -> bool:
        """
        Envia a mensagem de sinal formatada para o Telegram.
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados no arquivo .env!")
            print("\n[MOCK TELEGRAM ALERT - Bot não configurado no .env]:")
            print(self.format_signal_message(signal))
            print("-" * 50)
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": self.format_signal_message(signal),
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            result = response.json()
            if result.get("ok"):
                logger.info(f"Sinal enviado com sucesso para {signal.symbol}")
                return True
            else:
                logger.error(f"Erro Telegram API: {result.get('description')}")
                return False
        except Exception as e:
            logger.error(f"Exceção ao enviar mensagem para Telegram: {e}")
            return False
