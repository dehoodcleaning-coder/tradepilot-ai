import json
import logging
import sqlite3
import requests
import config
from analyst_agent import EvaluationResult

logger = logging.getLogger(__name__)

class LearningAgent:
    """
    📈 LEARNING AGENT
    Suporta persistência dupla:
    1. Supabase (PostgreSQL na Nuvem) via REST API
    2. SQLite (Banco Local de Fallback)
    """

    def __init__(self, db_path: str = "tradepilot_history.db"):
        self.db_path = db_path
        self.supabase_url = config.SUPABASE_URL
        self.supabase_key = config.SUPABASE_KEY
        self._init_sqlite()

    def _init_sqlite(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS setup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    direction TEXT,
                    alert_type TEXT,
                    total_score INTEGER,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    rr_ratio REAL,
                    score_breakdown TEXT,
                    technical_reasons TEXT,
                    risk_factors TEXT,
                    outcome TEXT DEFAULT 'PENDING',
                    result_r REAL DEFAULT 0.0
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao inicializar banco local SQLite: {e}")

    def record_evaluation(self, eval_res: EvaluationResult):
        opp = eval_res.opportunity
        payload = {
            "created_at": eval_res.timestamp.isoformat(),
            "symbol": opp.symbol,
            "direction": eval_res.direction,
            "alert_type": eval_res.alert_type,
            "total_score": int(eval_res.total_score),
            "entry_price": float(eval_res.entry_price),
            "stop_loss": float(eval_res.stop_loss),
            "take_profit_1": float(eval_res.take_profit_1),
            "take_profit_2": float(eval_res.take_profit_2),
            "rr_ratio": float(eval_res.rr_ratio),
            "score_breakdown": {k: int(v) for k, v in eval_res.score_breakdown.items()},
            "technical_reasons": list(eval_res.technical_reasons),
            "risk_factors": list(eval_res.risk_factors),
            "poi_low": float(opp.poi_low),
            "poi_high": float(opp.poi_high),
            "has_fvg": bool(opp.has_fvg),
            "has_sweep": bool(opp.has_sweep)
        }

        # 1. Tenta gravar no Supabase se as credenciais existirem
        if self.supabase_url and self.supabase_key and "your-project" not in self.supabase_url:
            try:
                endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/tradepilot_setups"
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if res.status_code in [200, 201]:
                    logger.info(f"✨ Setup gravado com SUCESSO no Supabase (Nuvem)! [{opp.symbol} | Score: {eval_res.total_score}]")
                    return
                else:
                    logger.warning(f"Falha Supabase REST ({res.status_code}): {res.text}. Usando fallback SQLite local.")
            except Exception as e:
                logger.error(f"Erro ao conectar com Supabase: {e}. Usando fallback SQLite local.")

        # 2. Fallback: Grava no SQLite Local
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO setup_history (
                    timestamp, symbol, direction, alert_type, total_score,
                    entry_price, stop_loss, take_profit_1, take_profit_2,
                    rr_ratio, score_breakdown, technical_reasons, risk_factors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload["created_at"],
                payload["symbol"],
                payload["direction"],
                payload["alert_type"],
                payload["total_score"],
                payload["entry_price"],
                payload["stop_loss"],
                payload["take_profit_1"],
                payload["take_profit_2"],
                payload["rr_ratio"],
                json.dumps(payload["score_breakdown"]),
                json.dumps(payload["technical_reasons"]),
                json.dumps(payload["risk_factors"])
            ))
            conn.commit()
            conn.close()
            logger.info(f"Setup registrado no banco local SQLite [Score: {eval_res.total_score} | {opp.symbol}]")
        except Exception as e:
            logger.error(f"Erro ao gravar no SQLite local: {e}")
