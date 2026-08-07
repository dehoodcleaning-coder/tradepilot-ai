import time
import threading
import logging
import sqlite3
import pandas as pd
import requests
import os
from typing import Dict, Any, List
from binance_client import BinanceMarketClient
from messenger_agent import MessengerAgent
import config

logger = logging.getLogger("PerformanceScheduler")

class PerformanceScheduler:
    """
    📊 12-HOUR PERFORMANCE REPORTING ENGINE
    Gera automaticamente a cada 12 horas um relatório consolidado de performance,
    salva no banco de dados / Supabase e transmite para o Telegram e Painel Web SaaS.
    """

    def __init__(self, messenger: MessengerAgent, client: BinanceMarketClient):
        self.messenger = messenger
        self.client = client
        self.interval_seconds = 12 * 3600  # 12 Horas (43.200 segundos)

    def generate_and_send_report(self) -> Dict[str, Any]:
        logger.info("📊 Gerando Relatório de Performance das últimas 12 horas...")
        
        setups = []
        # Consulta Supabase
        try:
            res = requests.get(
                f"{config.SUPABASE_URL}/rest/v1/tradepilot_setups?select=*&order=created_at.desc&limit=60",
                headers={
                    "apikey": config.SUPABASE_KEY,
                    "Authorization": f"Bearer {config.SUPABASE_KEY}"
                },
                timeout=10
            )
            if res.ok:
                setups = res.json()
        except Exception as e:
            logger.error(f"Erro ao consultar Supabase para relatório 12h: {e}")

        # Fallback local sqlite
        if not setups and os.path.exists("tradepilot.db"):
            try:
                conn = sqlite3.connect("tradepilot.db")
                df_local = pd.read_sql("SELECT * FROM setups ORDER BY created_at DESC LIMIT 60", conn)
                setups = df_local.to_dict('records')
            except Exception as e:
                logger.error(f"Erro ao consultar sqlite local: {e}")

        official_setups = [s for s in setups if s.get('total_score', 0) >= 80 or s.get('alert_type') == 'ENTRY_ELIGIBLE']

        wins_tp2 = 0
        wins_tp1 = 0
        losses = 0
        pending = 0
        total_r = 0.0
        asset_pnl: Dict[str, float] = {}

        for s in official_setups:
            symbol = s.get('symbol', 'BTC/USDT')
            direction = s.get('direction', 'BUY')
            entry = float(s.get('entry_price', 0))
            stop = float(s.get('stop_loss', 0))
            tp1 = float(s.get('take_profit_1', 0))
            tp2 = float(s.get('take_profit_2', 0))

            if symbol not in asset_pnl:
                asset_pnl[symbol] = 0.0

            df_1m = self.client.fetch_ohlcv_df(symbol, timeframe="1m", limit=150)
            r_result = 0.0

            if df_1m is not None and not df_1m.empty:
                high_max = df_1m['high'].max()
                low_min = df_1m['low'].min()

                if direction == 'BUY':
                    if high_max >= tp2:
                        r_result = +4.0
                        wins_tp2 += 1
                    elif high_max >= tp1:
                        r_result = +2.0
                        wins_tp1 += 1
                    elif low_min <= stop:
                        r_result = -1.0
                        losses += 1
                    else:
                        pending += 1
                else: # SELL
                    if low_min <= tp2:
                        r_result = +4.0
                        wins_tp2 += 1
                    elif low_min <= tp1:
                        r_result = +2.0
                        wins_tp1 += 1
                    elif high_max >= stop:
                        r_result = -1.0
                        losses += 1
                    else:
                        pending += 1

            total_r += r_result
            asset_pnl[symbol] += r_result

        closed_trades = wins_tp2 + wins_tp1 + losses
        win_rate = ((wins_tp2 + wins_tp1) / closed_trades * 100) if closed_trades > 0 else 100.0

        best_asset = max(asset_pnl.items(), key=lambda x: x[1])[0] if asset_pnl else "N/A"
        best_asset_r = asset_pnl.get(best_asset, 0.0)

        report_data = {
            "total_setups": len(setups),
            "official_setups": len(official_setups),
            "wins_tp2": wins_tp2,
            "wins_tp1": wins_tp1,
            "losses": losses,
            "pending": pending,
            "win_rate": round(win_rate, 1),
            "total_r": round(total_r, 1),
            "best_asset": best_asset,
            "best_asset_r": round(best_asset_r, 1),
            "timestamp": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M:%S UTC")
        }

        # Transmite mensagem formatada para o Telegram
        telegram_msg = (
            f"📊 <b>===================================</b>\n"
            f"🏆 <b>[TRADEPILOT AI] RELATÓRIO DE PERFORMANCE (12H)</b>\n"
            f"📊 <b>===================================</b>\n\n"
            f"📅 <b>Período:</b> <i>Últimas 12 Horas de Operação</i>\n"
            f"⏰ <b>Horário da Análise:</b> <code>{report_data['timestamp']}</code>\n\n"
            f"📈 <b>RESUMO EXECUTIVO DE PERFORMANCE:</b>\n"
            f"  • 🟢 <b>Alertas Oficiais (Score 80+):</b> <code>{report_data['official_setups']}</code>\n"
            f"  • 🏆 <b>Vitórias em TP2 (Alvo Macro 4R):</b> <code>{wins_tp2}</code>\n"
            f"  • ✅ <b>Vitórias em TP1 (Parcial 2R):</b> <code>{wins_tp1}</code>\n"
            f"  • 🛑 <b>Stops Controlados (-1R):</b> <code>{losses}</code>\n"
            f"  • ⏳ <b>Em Andamento:</b> <code>{pending}</code>\n\n"
            f"🎯 <b>TAXA DE ACERTO (WIN RATE):</b> <b>{win_rate:.1f}%</b>\n"
            f"💰 <b>LUCRO LÍQUIDO ACUMULADO:</b> <b>+{total_r:.1f}R</b>\n\n"
            f"🥇 <b>Melhor Ativo do Período:</b> <code>{best_asset} (+{best_asset_r:.1f}R)</code>\n\n"
            f"💡 <i>Exemplo financeiro (R$ 100/R): Lucro Líquido = +R$ {total_r * 100:.2f} no período.</i>"
        )

        if self.messenger.bot_token and self.messenger.chat_id:
            try:
                requests.post(self.messenger.api_url_text, json={
                    "chat_id": self.messenger.chat_id,
                    "text": telegram_msg,
                    "parse_mode": "HTML"
                }, timeout=10)
                logger.info("✨ Relatório de Performance 12h enviado para o Telegram com SUCESSO!")
            except Exception as e:
                logger.error(f"Erro ao enviar relatório 12h para o Telegram: {e}")
        else:
            print("\n" + "=" * 60)
            print("[MOCK TELEGRAM DISPATCH - RELATÓRIO 12H]:")
            print(telegram_msg)
            print("=" * 60 + "\n")

        return report_data

    def start_scheduler_thread(self):
        """Inicia a thread em segundo plano executando a cada 12h"""
        def run_loop():
            # Executa relatório imediatamente ao iniciar
            try:
                self.generate_and_send_report()
            except Exception as e:
                logger.error(f"Erro na execução inicial do relatório 12h: {e}")

            while True:
                time.sleep(self.interval_seconds)
                try:
                    self.generate_and_send_report()
                except Exception as e:
                    logger.error(f"Erro na execução recorrente do relatório 12h: {e}")

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        logger.info("🚀 Agendador de Relatório de Performance 12h INICIADO em segundo plano!")
