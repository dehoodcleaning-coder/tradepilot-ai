import os
from dotenv import load_dotenv

load_dotenv()

# App Info
PROJECT_NAME = "TradePilot AI"
VERSION = "1.0.0-Blueprint"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Mercado & Pares
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
SYMBOLS_ENV = os.getenv("SYMBOLS")
if SYMBOLS_ENV:
    SYMBOLS = [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]
else:
    SYMBOLS = DEFAULT_SYMBOLS

# Timeframes
CONTEXT_TIMEFRAME = "15m"   # Contexto Macro da Estrutura
STRUCTURE_TIMEFRAME = "5m"  # Mapeamento do POI, FVG e Liquidez
TRIGGER_TIMEFRAME = "1m"    # Gatilho de Entrada / CHoCH

# Thresholds do Sistema de Pontuação (0-100 pts)
PRE_ALERT_MIN_SCORE = 65    # Score mínimo para Pró-Alerta (Setup em Formação)
ENTRY_ALERT_MIN_SCORE = 80  # Score mínimo para Alerta de Entrada Oficial
MIN_RISK_REWARD = 3.0       # Relação R:R mínima aceita (3.0 = 3R)

# Loop & Rate Limiting
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
COOLDOWN_MINUTES_PER_SYMBOL = 15
