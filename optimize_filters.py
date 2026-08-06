import requests
import pandas as pd
import numpy as np
import config
from evaluate_outcomes import OutcomeEvaluator

def run_filter_optimization():
    print("=" * 80)
    print("🔬 ANÁLISE QUANTITATIVA E OTIMIZAÇÃO DE PERFORMANCE (TRADEPILOT AI)")
    print("=" * 80)

    evaluator = OutcomeEvaluator()
    setups = evaluator.fetch_setups_supabase()
    if not setups:
        setups = evaluator.fetch_setups_sqlite()

    if not setups:
        print("Nenhum setup encontrado.")
        return

    evaluated_data = []
    for s in setups:
        res = evaluator.evaluate_setup_outcome(s)
        s['evaluated_outcome'] = res['outcome']
        s['evaluated_result_r'] = res['result_r']
        evaluated_data.append(s)

    df = pd.DataFrame(evaluated_data)
    closed_df = df[df['evaluated_outcome'] != 'PENDING'].copy()

    # 1. Comparativo por Score (Score >= 80 vs Score < 80)
    df_official = closed_df[closed_df['total_score'] >= 80]
    df_pre_alert = closed_df[closed_df['total_score'] < 80]

    def get_metrics(df_sub, label):
        if df_sub.empty:
            return f"• {label}: Sem operações."
        wins = len(df_sub[df_sub['evaluated_outcome'].str.contains('WIN')])
        losses = len(df_sub[df_sub['evaluated_outcome'] == 'STOPPED'])
        total_r = df_sub['evaluated_result_r'].sum()
        win_rate = (wins / len(df_sub)) * 100
        return f"• {label}: Win Rate = {win_rate:.1f}% | Lucro = {total_r:+.1f}R | Total Trades = {len(df_sub)} (Vítórias: {wins}, Stops: {losses})"

    print("\n📊 1. ANÁLISE POR CLASSIFICAÇÃO DE SCORE:")
    print(get_metrics(closed_df, "Todos os Sinais Auditados (Score >= 65)"))
    print(get_metrics(df_official, "Apenas ALERTAS OFICIAIS (Score >= 80)"))
    print(get_metrics(df_pre_alert, "Apenas PRÓ-ALERTAS (Score 65-79)"))

    # 2. Comparativo por Presença de Varredura de Liquidez (has_sweep)
    if 'has_sweep' in closed_df.columns:
        df_sweep = closed_df[closed_df['has_sweep'] == True]
        df_no_sweep = closed_df[closed_df['has_sweep'] == False]

        print("\n📊 2. ANÁLISE POR CAPTURA DE LIQUIDEZ (SWEEP DOS PIVÔS):")
        print(get_metrics(df_sweep, "Setups COM Sweep de Liquidez do Pivô"))
        print(get_metrics(df_no_sweep, "Setups SEM Sweep de Liquidez"))

    print("\n" + "=" * 80)

if __name__ == "__main__":
    run_filter_optimization()
