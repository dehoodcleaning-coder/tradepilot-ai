import time
import logging
from typing import Dict, Any
from binance_client import BinanceMarketClient
from scout_agent import ScoutAgent
from analyst_agent import AnalystAgent
from messenger_agent import MessengerAgent
from learning_agent import LearningAgent
from performance_scheduler import PerformanceScheduler
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TradePilotMain")

def main():
    logger.info("🚀 INICIALIZANDO TRADEPILOT AI MULTI-AGENT SYSTEM (VERSÃO THREADED PRO)")
    logger.info(f"📊 Símbolos Monitorados: {config.SYMBOLS}")

    client = BinanceMarketClient()
    scout = ScoutAgent(client)
    analyst = AnalystAgent()
    messenger = MessengerAgent(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    learning = LearningAgent()

    # Inicializa e dispara o Agendador de Performance a cada 12 Horas
    perf_scheduler = PerformanceScheduler(messenger, client)
    perf_scheduler.start_scheduler_thread()

    # Rastreia cooldown por símbolo e pré-alertas ativos
    last_alert_time: Dict[str, float] = {}
    active_pre_alerts: Dict[str, Dict[str, Any]] = {} # symbol -> {setup_id, telegram_msg_id, timestamp}

    logger.info("✅ Todos os Agentes Inicializados. Iniciando varredura contínua do mercado 24/7...")

    while True:
        try:
            for symbol in config.SYMBOLS:
                current_time = time.time()
                
                # Respeita o Cooldown de 15 min por símbolo
                if symbol in last_alert_time:
                    elapsed_min = (current_time - last_alert_time[symbol]) / 60.0
                    if elapsed_min < config.COOLDOWN_MINUTES_PER_SYMBOL:
                        continue

                # 1. Scout Agent busca a oportunidade
                opp = scout.scan_symbol(symbol)
                if not opp:
                    continue

                # 2. Analyst Agent avalia e pontua o setup
                eval_res = analyst.evaluate_opportunity(opp)
                if eval_res.alert_type == 'REJECTED':
                    continue

                # 3. Verifica se existe um Pró-Alerta ativo para encadear a resposta (Threading)
                active_pre = active_pre_alerts.get(symbol)
                reply_msg_id = active_pre['telegram_msg_id'] if active_pre else None

                # 4. Messenger Agent dispara o alerta (FOTO + HTML + Reply)
                sent_msg_id = messenger.send_alert(eval_res, reply_to_message_id=reply_msg_id)

                if sent_msg_id:
                    # 5. Learning Agent persiste o setup com o ID da mensagem no Telegram
                    setup_id = learning.save_setup(eval_res, telegram_message_id=sent_msg_id)
                    last_alert_time[symbol] = current_time

                    if eval_res.alert_type == 'PRE_ALERT':
                        active_pre_alerts[symbol] = {
                            "setup_id": setup_id,
                            "telegram_msg_id": sent_msg_id,
                            "timestamp": current_time
                        }
                    elif eval_res.alert_type == 'ENTRY_ELIGIBLE':
                        # Limpa o pré-alerta ativo pois a entrada oficial já foi confirmada
                        if symbol in active_pre_alerts:
                            del active_pre_alerts[symbol]

            # Intervalo de varredura (30 segundos)
            time.sleep(30)

        except KeyboardInterrupt:
            logger.info("🛑 TradePilot AI encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"Erro inesperado no loop principal: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
