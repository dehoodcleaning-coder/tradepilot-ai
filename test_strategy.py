import sys
import logging
from binance_client import BinanceMarketClient
from smc_analyzer import SMCAnalyzer
from telegram_bot import TelegramSignalNotifier
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_dry_run_test():
    print("=" * 70)
    print("🔍 TESTE DIAGNÓSTICO: ANÁLISE DE POI PEIXE GRANDE (BINANCE LIVE DATA)")
    print("=" * 70)

    client = BinanceMarketClient()
    analyzer = SMCAnalyzer(buffer_percent=config.BUFFER_PERCENT)
    notifier = TelegramSignalNotifier("", "")  # Notificador mock

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

    for symbol in symbols:
        print(f"\n📊 Analisando {symbol}...")
        df_5m = client.fetch_ohlcv_df(symbol, timeframe="5m", limit=150)
        df_1m = client.fetch_ohlcv_df(symbol, timeframe="1m", limit=150)

        if df_5m is None or df_1m is None:
            print(f"❌ Falha ao carregar dados da Binance para {symbol}")
            continue

        price_5m = df_5m['close'].iloc[-1]
        print(f"   Preço Atual: {price_5m:.4f}")

        # Identifica POIs no 5m
        pois = analyzer.identify_5m_pois(symbol, df_5m)
        print(f"   POIs Encontrados no 5m: {len(pois)}")

        for i, poi in enumerate(pois, 1):
            fvg_str = "FVG ✅" if poi.has_fvg else "Sem FVG"
            sweep_str = "Sweep ✅" if poi.has_liquidity_sweep else "Sem Sweep"
            print(f"   └─ POI #{i} ({poi.direction}): [{poi.low:.4f} - {poi.high:.4f}] | {fvg_str} | {sweep_str} | Criado em: {poi.created_at}")

        # Testa geração de sinal
        signal = analyzer.analyze_market(symbol, df_5m, df_1m)
        if signal:
            print(f"\n   ⚡ SINAL DETECTADO EM TEMPO REAL!")
            print(notifier.format_signal_message(signal))
        else:
            print("   ℹ️ Nenhuma confluência de entrada ativa no momento exato deste candle.")

    print("\n" + "=" * 70)
    print("✅ TESTE DIAGNÓSTICO CONCLUÍDO COM SUCESSO!")
    print("=" * 70)

if __name__ == "__main__":
    run_dry_run_test()
