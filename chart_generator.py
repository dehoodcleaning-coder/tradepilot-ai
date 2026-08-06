import matplotlib
matplotlib.use('Agg') # Render sem GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import logging
import os
from typing import Optional
from analyst_agent import EvaluationResult

logger = logging.getLogger(__name__)

class ChartGenerator:
    """
    📊 CHART GENERATOR
    Gera um gráfico visual de velas (Candlesticks) em modo escuro (TradingView Style)
    demarcando a Zona do POI, Preço de Entrada, Stop Loss e Take Profit.
    """

    @staticmethod
    def generate_signal_chart(eval_res: EvaluationResult, output_filename: str = "temp_chart.png") -> Optional[str]:
        try:
            df = eval_res.opportunity.df_5m.tail(40).copy()
            if df.empty:
                return None

            # Estilo Dark Mode TradingView
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
            fig.patch.set_facecolor('#131722')
            ax.set_facecolor('#131722')

            # Renderiza os Candlesticks
            for i in range(len(df)):
                open_p = df['open'].iloc[i]
                close_p = df['close'].iloc[i]
                high_p = df['high'].iloc[i]
                low_p = df['low'].iloc[i]

                color = '#26a69a' if close_p >= open_p else '#ef5350' # Verde / Vermelho TradingView

                # Pavio
                ax.plot([i, i], [low_p, high_p], color=color, linewidth=1.2)
                # Corpo do Candle
                height = abs(close_p - open_p)
                bottom = min(open_p, close_p)
                rect = patches.Rectangle((i - 0.35, bottom), 0.7, height if height > 0 else 0.0001,
                                         linewidth=0, edgecolor=None, facecolor=color)
                ax.add_patch(rect)

            # Demarca a Zona do POI
            poi_low = eval_res.opportunity.poi_low
            poi_high = eval_res.opportunity.poi_high
            poi_color = '#26a69a' if eval_res.direction == 'BUY' else '#ef5350'
            
            ax.axhspan(poi_low, poi_high, color=poi_color, alpha=0.25, label=f"POI 5m [{poi_low:.2f} - {poi_high:.2f}]")

            # Linhas de Nível Operacional
            entry_color = '#00E676' if eval_res.direction == 'BUY' else '#FF5252'
            ax.axhline(eval_res.entry_price, color=entry_color, linestyle='--', linewidth=1.5, label=f"Entrada: {eval_res.entry_price:.2f}")
            ax.axhline(eval_res.stop_loss, color='#FF1744', linestyle='-', linewidth=1.5, label=f"Stop Loss: {eval_res.stop_loss:.2f}")
            ax.axhline(eval_res.take_profit_1, color='#00B0FF', linestyle=':', linewidth=1.5, label=f"TP1 (2R): {eval_res.take_profit_1:.2f}")
            ax.axhline(eval_res.take_profit_2, color='#651FFF', linestyle='-.', linewidth=1.5, label=f"TP2 (Macro): {eval_res.take_profit_2:.2f}")

            # Título e Legendas
            dir_str = "COMPRA (LONG)" if eval_res.direction == 'BUY' else "VENDA (SHORT)"
            plt.title(f"TradePilot AI - {eval_res.opportunity.symbol} [{dir_str}] - Score: {eval_res.total_score}/100\n{eval_res.setup_scenario}",
                      fontsize=11, color='#FFFFFF', fontweight='bold', pad=12)

            ax.grid(True, color='#2a2e39', linestyle='--', linewidth=0.5, alpha=0.5)
            ax.legend(loc='upper left', facecolor='#1e222d', edgecolor='#2a2e39', fontsize=8, labelcolor='#FFFFFF')

            # Eixo X / Y
            ax.set_xticks([])
            ax.set_ylabel("Preço", color='#848e9c', fontsize=9)
            ax.tick_params(colors='#848e9c')

            plt.tight_layout()
            plt.savefig(output_filename, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
            plt.close()

            logger.info(f"Gráfico gerado com sucesso: {output_filename}")
            return output_filename
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico visual: {e}")
            return None
