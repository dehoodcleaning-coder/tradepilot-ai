import sqlite3
import requests
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any
from binance_client import BinanceMarketClient
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OutcomeEvaluator")

class OutcomeEvaluator:
    """
    📊 OUTCOME EVALUATOR
    Audita todos os sinais e setups registrados no Supabase / SQLite local,
    analisa a ação de preço subsequente na Binance e determina se o trade atingiu
    Take Profit 1 (2R), Take Profit 2 (4R) ou Stop Loss.
    """

    def __init__(self, db_path: str = "tradepilot_history.db"):
        self.db_path = db_path
        self.client = BinanceMarketClient()

    def fetch_setups_sqlite() -> List[Dict[str, Any]]:
        setups = []
        try:
            conn = sqlite3.connect("tradepilot_history.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM setup_history ORDER BY id DESC")
            rows = cursor.fetchall()
            for r in rows:
                setups.append(dict(r))
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao buscar do SQLite: {e}")
        return setups

    def fetch_setups_supabase(self) -> List[Dict[str, Any]]:
        setups = []
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                endpoint = f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/tradepilot_setups?select=*&order=created_at.desc"
                headers = {
                    "apikey": config.SUPABASE_KEY,
                    "Authorization": f"Bearer {config.SUPABASE_KEY}"
                }
                res = requests.get(endpoint, headers=headers, timeout=10)
                if res.status_code == 200:
                    setups = res.json()
            except Exception as e:
                logger.error(f"Erro ao consultar Supabase: {e}")
        return setups

    def evaluate_setup_outcome(self, setup: Dict[str, Any]) -> Dict[str, Any]:
        symbol = setup['symbol']
        direction = setup['direction']
        entry_price = float(setup['entry_price'])
        stop_loss = float(setup['stop_loss'])
        tp1 = float(setup['take_profit_1'])
        tp2 = float(setup['take_profit_2'])

        # Busca dados de candles 1m da Binance após a geração do sinal
        df_1m = self.client.fetch_ohlcv_df(symbol, timeframe="1m", limit=300)
        if df_1m is None or df_1m.empty:
            return {'outcome': 'UNKNOWN', 'result_r': 0.0, 'detail': 'Sem dados suficientes'}

        # Percorre as velas após o sinal para verificar a hitting order
        outcome = 'PENDING'
        result_r = 0.0

        for i in range(len(df_1m)):
            high = df_1m['high'].iloc[i]
            low = df_1m['low'].iloc[i]

            if direction == 'BUY':
                # Verifica Stop Loss
                if low <= stop_loss:
                    outcome = 'STOPPED'
                    result_r = -1.0
                    break
                # Verifica TP2 (Alvo Máximo 4R)
                elif high >= tp2:
                    outcome = 'WIN_TP2'
                    result_r = 4.0
                    break
                # Verifica TP1 (2R)
                elif high >= tp1:
                    outcome = 'WIN_TP1'
                    result_r = 2.0
                    # Continua para ver se chega ao TP2

            elif direction == 'SELL':
                # Verifica Stop Loss
                if high >= stop_loss:
                    outcome = 'STOPPED'
                    result_r = -1.0
                    break
                # Verifica TP2 (Alvo Máximo 4R)
                elif low <= tp2:
                    outcome = 'WIN_TP2'
                    result_r = 4.0
                    break
                # Verifica TP1 (2R)
                elif low <= tp1:
                    outcome = 'WIN_TP1'
                    result_r = 2.0
                    # Continua para ver se chega ao TP2

        return {'outcome': outcome, 'result_r': result_r, 'detail': f"Resultado: {outcome} ({result_r:+.1f}R)" if result_r != 0 else outcome}

    def run_full_audit(self):
        print("=" * 80)
        print("📊 AUDITORIA DE PERFORMANCE TRADEPILOT AI - RESULTADO DOS SINAIS (TAKE VS STOP)")
        print("=" * 80)

        # Tenta Supabase primeiro, fallback SQLite
        setups = self.fetch_setups_supabase()
        if not setups:
            setups = self.fetch_setups_sqlite()

        if not setups:
            print("⚠️ Nenhum histórico de sinal encontrado no banco de dados ainda.")
            return

        total_signals = len(setups)
        wins_tp1 = 0
        wins_tp2 = 0
        losses = 0
        pending = 0
        total_r = 0.0

        print(f"\nTotal de Sinais Gravados: {total_signals}\n")
        print(f"{'ID':<5} | {'Data/Hora':<19} | {'Ativo':<9} | {'Tipo':<6} | {'Score':<5} | {'Entrada':<10} | {'Resultado':<10} | {'Retorno R':<9}")
        print("-" * 80)

        for s in setups:
            sid = s.get('id', '-')
            ts = str(s.get('created_at' if 'created_at' in s else 'timestamp', ''))[:19].replace('T', ' ')
            symbol = s.get('symbol', '')
            direction = s.get('direction', '')
            score = s.get('total_score', 0)
            entry = float(s.get('entry_price', 0.0))

            res = self.evaluate_setup_outcome(s)
            outcome = res['outcome']
            r_val = res['result_r']

            if outcome == 'WIN_TP2':
                wins_tp2 += 1
                wins_tp1 += 1
                total_r += r_val
                status_str = "🟢 WIN (TP2)"
            elif outcome == 'WIN_TP1':
                wins_tp1 += 1
                total_r += r_val
                status_str = "🟢 WIN (TP1)"
            elif outcome == 'STOPPED':
                losses += 1
                total_r += r_val
                status_str = "🔴 STOPPED"
            else:
                pending += 1
                status_str = "⏳ PENDENTE"

            print(f"{sid:<5} | {ts:<19} | {symbol:<9} | {direction:<6} | {score:<5} | {entry:<10.2f} | {status_str:<10} | {r_val:+6.1f}R")

        closed_trades = wins_tp1 + losses
        win_rate = (wins_tp1 / closed_trades * 100) if closed_trades > 0 else 0.0

        print("\n" + "=" * 80)
        print("📈 RESUMO CONSOLIDADO DE PERFORMANCE")
        print("=" * 80)
        print(f"🎯 Total de Trades Finalizados: {closed_trades}")
        print(f"✅ Vencedores (TP1/TP2): {wins_tp1} (TP2 Total: {wins_tp2})")
        print(f"❌ Perdedores (Stop): {losses}")
        print(f"⏳ Em Andamento (Pendentes): {pending}")
        print(f"🏆 Taxa de Acerto (Win Rate): {win_rate:.1f}%")
        print(f"💰 Lucro Acumulado em R: {total_r:+6.1f}R")
        print("=" * 80)

if __name__ == "__main__":
    evaluator = OutcomeEvaluator()
    evaluator.run_full_audit()
