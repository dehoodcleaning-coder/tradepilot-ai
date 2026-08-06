import os
from dotenv import load_dotenv

load_dotenv()

# Configurações do Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# 📊 Lista de Ativos Monitorados (6 Paridades de Alta Liquidez)
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,ADA/USDT").split(",")

# Timeframes da Estratégia SMC (Peixe Grande Trading)
CONTEXT_TIMEFRAME = "15m"   # Estrutura Macro
STRUCTURE_TIMEFRAME = "5m"   # POI, OB, FVG, Liquidez
TRIGGER_TIMEFRAME = "1m"     # CHoCH Gatilho de Entrada

# Parâmetros de Avaliação de Pontuação (Score Model)
PRE_ALERT_MIN_SCORE = 65     # Envia Pró-Alerta (Setup em Formação)
ENTRY_ALERT_MIN_SCORE = 80   # Envia Alerta Oficial de Entrada (Setup Elegível)

# Parâmetros de Gestão de Risco
MIN_RISK_REWARD = 3.0        # Mínimo Risco:Retorno (1:3)
COOLDOWN_MINUTES_PER_SYMBOL = 15 # Evita spambar o mesmo par num curto intervalo
