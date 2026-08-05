import sys
import logging
from binance_client import BinanceMarketClient
from scout_agent import ScoutAgent
from analyst_agent import AnalystAgent
from messenger_agent import MessengerAgent
from learning_agent import LearningAgent
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

def test_tradepilot_multi_agent():
    print("=" * 75)
    print("🤖 TESTE DE INTEGRAÇÃO MULTI-AGENTE: TRADEPILOT AI (VERSÃO BLUEPRINT)")
    print("=" * 75)

    client = BinanceMarketClient()
    scout = ScoutAgent(client)
    analyst = AnalystAgent()
    messenger = MessengerAgent(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    learning = LearningAgent("test_tradepilot_history.db")

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

    for symbol in symbols:
        print(f"\n🔍 [SCOUT AGENT] Escaneando {symbol}...")
        opp = scout.scan_symbol(symbol)
        if not opp:
            print(f"   ℹ️ Nenhuma estrutura inicial de POI em desenvolvimento para {symbol}.")
            continue

        print(f"   📍 [SCOUT AGENT] Oportunidade detectada em {symbol} ({opp.direction})!")
        print(f"      Preço Atual: {opp.current_price:.4f} | Faixa POI 5m: [{opp.poi_low:.4f} - {opp.poi_high:.4f}]")

        print(f"🧠 [ANALYST AGENT] Avaliando modelo de 100 pontos...")
        eval_res = analyst.evaluate_opportunity(opp)
        print(f"   ⭐ SCORE TOTAL: {eval_res.total_score} / 100 PTS | TIPO: {eval_res.alert_type}")
        print("   📊 Detalhamento da Pontuação:")
        for k, v in eval_res.score_breakdown.items():
            print(f"      • {k}: {v} pts")

        # Registra no Learning Agent
        learning.record_evaluation(eval_res)

        print(f"\n📢 [MESSENGER AGENT] Enviando Alerta {eval_res.alert_type} para o Telegram...")
        messenger.send_alert(eval_res)

    print("\n" + "=" * 75)
    print("✅ TESTE DO TRADEPILOT AI MULTI-AGENTE CONCLUÍDO COM SUCESSO!")
    print("=" * 75)

if __name__ == "__main__":
    test_tradepilot_multi_agent()
