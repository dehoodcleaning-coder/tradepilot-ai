import os
import sqlite3
import requests
import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from analyst_agent import EvaluationResult
import config

logger = logging.getLogger(__name__)

class LearningAgent:
    """
    📈 LEARNING AGENT (THREADING & PERSISTENCE ENGINE)
    Armazena todos os setups, rastreia os IDs de mensagem do Telegram (telegram_message_id)
    para permitir respostas diretas (Reply-to-Message) nos tópicos de alertas e invalidações.
    """

    def __init__(self, db_path: str = "tradepilot_history.db"):
        self.db_path = db_path
        self.init_sqlite()

    def init_sqlite(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS setup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    direction TEXT,
                    total_score INTEGER,
                    alert_type TEXT,
                    setup_scenario TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    rr_ratio REAL,
                    poi_low REAL,
                    poi_high REAL,
                    has_sweep INTEGER,
                    has_fvg INTEGER,
                    telegram_message_id INTEGER,
                    outcome TEXT DEFAULT 'PENDING',
                    result_r REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao inicializar SQLite: {e}")

    def save_setup(self, eval_res: EvaluationResult, telegram_message_id: Optional[int] = None) -> Optional[int]:
        opp = eval_res.opportunity
        
        # 1. Salva no SQLite
        setup_id = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO setup_history (
                    symbol, direction, total_score, alert_type, setup_scenario,
                    entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio,
                    poi_low, poi_high, has_sweep, has_fvg, telegram_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp.symbol, eval_res.direction, eval_res.total_score, eval_res.alert_type, eval_res.setup_scenario,
                eval_res.entry_price, eval_res.stop_loss, eval_res.take_profit_1, eval_res.take_profit_2, eval_res.rr_ratio,
                opp.poi_low, opp.poi_high, 1 if opp.has_sweep else 0, 1 if opp.has_fvg else 0, telegram_message_id
            ))
            conn.commit()
            setup_id = cursor.lastrowid
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao gravar no SQLite: {e}")

        # 2. Salva no Supabase REST API
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                endpoint = f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/tradepilot_setups"
                headers = {
                    "apikey": config.SUPABASE_KEY,
                    "Authorization": f"Bearer {config.SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                payload = {
                    "symbol": opp.symbol,
                    "direction": eval_res.direction,
                    "total_score": eval_res.total_score,
                    "alert_type": eval_res.alert_type,
                    "setup_scenario": eval_res.setup_scenario,
                    "entry_price": eval_res.entry_price,
                    "stop_loss": eval_res.stop_loss,
                    "take_profit_1": eval_res.take_profit_1,
                    "take_profit_2": eval_res.take_profit_2,
                    "rr_ratio": eval_res.rr_ratio,
                    "poi_low": opp.poi_low,
                    "poi_high": opp.poi_high,
                    "has_sweep": opp.has_sweep,
                    "has_fvg": opp.has_fvg,
                    "telegram_message_id": telegram_message_id
                }
                res = requests.post(endpoint, json=payload, headers=headers, timeout=5)
                if res.status_code in (200, 201):
                    logger.info(f"✨ Setup gravado com SUCESSO no Supabase (Nuvem)! [{opp.symbol} | Score: {eval_res.total_score}]")
            except Exception as e:
                logger.error(f"Erro ao salvar no Supabase REST API: {e}")

        return setup_id

    def update_telegram_message_id(self, setup_id: int, message_id: int):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE setup_history SET telegram_message_id = ? WHERE id = ?", (message_id, setup_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao atualizar telegram_message_id no SQLite: {e}")

    def find_active_pre_alert(self, symbol: str, poi_low: float, poi_high: float) -> Optional[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM setup_history 
                WHERE symbol = ? AND alert_type = 'PRE_ALERT' 
                ORDER BY id DESC LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
            conn.close()

            if row:
                r_dict = dict(row)
                # Verifica se o POI é o mesmo (margem de 0.2%)
                if abs(r_dict['poi_low'] - poi_low) / poi_low < 0.002:
                    return r_dict
        except Exception as e:
            logger.error(f"Erro ao buscar pré-alerta ativo: {e}")
        return None
