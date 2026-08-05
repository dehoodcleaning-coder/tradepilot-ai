import time
import datetime
import logging
from typing import Dict

import config
from binance_client import BinanceMarketClient
from scout_agent import ScoutAgent
from analyst_agent import AnalystAgent
from messenger_agent import MessengerAgent
from learning_agent import LearningAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("TradePilotAI")

def main():
    print("=" * 70)
    print(f"🚀 INICIANDO {config.PROJECT_NAME} (VERSÃO {config.VERSION})")
    print("=" * 70)
    print(f"📌 Mercado / Pares: {', '.join(config.SYMBOLS)}")
    print(f"⏱ Timeframes: Contexto 15m | Estrutura 5m | Gatilho 1m")
    print(f"⭐ Scores: Pró-Alerta >= {config.PRE_ALERT_MIN_SCORE} pts | Entrada Oficial >= {config.ENTRY_ALERT_MIN_SCORE} pts (R:R >= 3:1)")
    print("=" * 70)

    client = BinanceMarketClient()
    scout = ScoutAgent(client)
    analyst = AnalystAgent()
    messenger = MessengerAgent(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    learning = LearningAgent()

    last_alert_time: Dict[str, datetime.datetime] = {}

    while True:
        try:
            logger.info("Escaneando mercado com a rede de agentes TradePilot AI...")
            for symbol in config.SYMBOLS:
                now = datetime.datetime.now()

                # Cooldown de Alerta para o mesmo símbolo
                if symbol in last_alert_time:
                    elapsed = (now - last_alert_time[symbol]).total_seconds() / 60.0
                    if elapsed < config.COOLDOWN_MINUTES_PER_SYMBOL:
                        continue

                # 1. SCOUT AGENT: Escaneia o mercado
                opp = scout.scan_symbol(symbol)
                if not opp:
                    continue

                # 2. ANALYST AGENT: Avalia no modelo de 100 pontos
                eval_res = analyst.evaluate_opportunity(opp)

                # Se o setup for rejeitado (score < 65), ignora
                if eval_res.alert_type == 'REJECTED':
                    continue

                # 3. LEARNING AGENT: Registra para histórico e métricas de win rate
                learning.record_evaluation(eval_res)

                # 4. MESSENGER AGENT: Dispara notificação formatada para o Telegram
                logger.info(f"✨ OPORTUNIDADE DETECTADA [{eval_res.alert_type}]: {symbol} (Score: {eval_res.total_score}/100)")
                messenger.send_alert(eval_res)
                last_alert_time[symbol] = now

            time.sleep(config.POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n👋 TradePilot AI encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
