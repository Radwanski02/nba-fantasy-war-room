from __future__ import annotations
import pandas as pd

def available_board(ranked: pd.DataFrame, drafted_ids: set[int], n=50) -> pd.DataFrame:
    x=ranked.copy()
    if "espn_id" in x:
        x=x[~pd.to_numeric(x.espn_id,errors="coerce").isin(drafted_ids)]
    cols=["model_rank","player","espn_rank","espn_adp","value_gap","market_label","quant_score","proj_games","injury_status","reason"]
    cols=[c for c in cols if c in x]
    return x[cols].head(n).reset_index(drop=True)
