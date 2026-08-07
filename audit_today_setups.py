import sqlite3
import pandas as pd
import requests
import os
from binance_client import BinanceMarketClient

SUPABASE_URL = "https://skrnjqpoxwjuaffoctsp.supabase.co"
SUPABASE_KEY = "sb_publishable_mNTPWQkt-KxFUdGn7qZ0VQ_jCGCh76a"

def audit_today():
    print("=" * 80)
    print("📊 AUDITORIA DE SETUPS E RESULTADOS (ÚLTIMAS 24 HORAS)")
    print("=" * 80)

    client = BinanceMarketClient()
    setups = []

    # 1. Consulta Supabase Cloud
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/tradepilot_setups?select=*&order=created_at.desc&limit=50", headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }, timeout=10)
        if res.ok:
            setups = res.json()
    except Exception as e:
        print(f"Erro ao buscar do Supabase: {e}")

    # 2. Se o Supabase estiver limpo, consulta banco local tradepilot.db
    if not setups and os.path.exists("tradepilot.db"):
        conn = sqlite3.connect("tradepilot.db")
        df_local = pd.read_sql("SELECT * FROM setups ORDER BY created_at DESC LIMIT 50", conn)
        setups = df_local.to_dict('records')

    if not setups:
        print("Nenhum setup registrado no banco nas últimas 24h. Gerando avaliação com setups de teste ativas.")
        return

    # Filtra apenas alertas oficiais (Score >= 80)
    official_setups = [s for s in setups if s.get('total_score', 0) >= 80 or s.get('alert_type') == 'ENTRY_ELIGIBLE']
    pre_alerts = [s for s in setups if s not in official_setups]

    print(f"\n Total de Oportunidades Monitoradas: {len(setups)}")
    print(f"  🟢 Alertas Oficiais de Entrada (Score 80+): {len(official_setups)}")
    print(f"  👀 Pró-Alertas em Acompanhamento (Score <80): {len(pre_alerts)}\n")

    wins_tp2 = 0
    wins_tp1 = 0
    losses = 0
    pending = 0
    total_r = 0.0

    print("-" * 80)
    print(f"{'HORA':<10} | {'ATIVO':<10} | {'DIREÇÃO':<6} | {'SCORE':<5} | {'ENTRADA':<9} | {'RESULTADO':<15} | {'P&L (R)'}")
    print("-" * 80)

    for s in official_setups:
        symbol = s.get('symbol', 'BTC/USDT')
        direction = s.get('direction', 'BUY')
        entry = float(s.get('entry_price', 0))
        stop = float(s.get('stop_loss', 0))
        tp1 = float(s.get('take_profit_1', 0))
        tp2 = float(s.get('take_profit_2', 0))
        score = s.get('total_score', 80)
        time_str = str(s.get('created_at', ''))[-8:-3] if s.get('created_at') else "Hoje"

        # Busca histórico recente do candle
        df_1m = client.fetch_ohlcv_df(symbol, timeframe="1m", limit=200)

        outcome = "PENDENTE ⏳"
        r_result = 0.0

        if df_1m is not None and not df_1m.empty:
            high_max = df_1m['high'].max()
            low_min = df_1m['low'].min()

            if direction == 'BUY':
                if high_max >= tp2:
                    outcome = "WIN (TP2 4R) 🏆"
                    r_result = +4.0
                    wins_tp2 += 1
                elif high_max >= tp1:
                    outcome = "WIN (TP1 2R) ✅"
                    r_result = +2.0
                    wins_tp1 += 1
                elif low_min <= stop:
                    outcome = "STOP LOSS 🛑"
                    r_result = -1.0
                    losses += 1
                else:
                    outcome = "EM ANDAMENTO ⏳"
                    pending += 1
            else: # SELL
                if low_min <= tp2:
                    outcome = "WIN (TP2 4R) 🏆"
                    r_result = +4.0
                    wins_tp2 += 1
                elif low_min <= tp1:
                    outcome = "WIN (TP1 2R) ✅"
                    r_result = +2.0
                    wins_tp1 += 1
                elif high_max >= stop:
                    outcome = "STOP LOSS 🛑"
                    r_result = -1.0
                    losses += 1
                else:
                    outcome = "EM ANDAMENTO ⏳"
                    pending += 1

        total_r += r_result
        r_str = f"+{r_result:.1f}R" if r_result > 0 else (f"{r_result:.1f}R" if r_result < 0 else "0.0R")
        print(f"{time_str:<10} | {symbol:<10} | {direction:<6} | {score:<5} | ${entry:<8.2f} | {outcome:<15} | {r_str}")

    print("-" * 80)
    closed_trades = wins_tp2 + wins_tp1 + losses
    win_rate = ((wins_tp2 + wins_tp1) / closed_trades * 100) if closed_trades > 0 else 100.0

    print(f"\n RESUMO DE PERFORMANCE DO DIA:")
    print(f"  🏆 Ganhos em TP2 (Alvo Macro 4R): {wins_tp2}")
    print(f"  ✅ Ganhos em TP1 (Parcial 2R): {wins_tp1}")
    print(f"  🛑 Stop Loss: {losses}")
    print(f"  ⏳ Em Andamento: {pending}")
    print(f"  🎯 Taxa de Acerto (Win Rate): {win_rate:.1f}%")
    print(f"  💰 RETORNO ACUMULADO NO DIA: +{total_r:.1f}R  (Ex: R$ 100/R = +R$ {total_r * 100:.2f})")
    print("=" * 80)

if __name__ == "__main__":
    audit_today()
