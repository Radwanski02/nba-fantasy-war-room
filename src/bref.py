from __future__ import annotations
import time
import pandas as pd

URLS = {
 "per_game":"https://www.basketball-reference.com/leagues/NBA_{season}_per_game.html",
 "advanced":"https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html",
 "per_poss":"https://www.basketball-reference.com/leagues/NBA_{season}_per_poss.html",
}

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
    df = df[df["Player"].notna() & (df["Player"]!="Player")].copy()
    df["Player"] = df["Player"].str.replace(r"\*", "", regex=True)
    # Traded players appear multiple times. Prefer TOT, else largest minutes/games row.
    if "Team" in df.columns:
        df["_tot"]=(df["Team"]=="TOT").astype(int)
        sort_cols=["Player","_tot"] + (["MP"] if "MP" in df.columns else (["G"] if "G" in df.columns else []))
        df=df.sort_values(sort_cols, ascending=[True,False]+[False]*(len(sort_cols)-2)).drop_duplicates("Player")
        df=df.drop(columns=["_tot"])
    return df

def fetch_table(season: int, kind: str) -> pd.DataFrame:
    tables = pd.read_html(URLS[kind].format(season=season), attrs={"id":f"{kind}_stats"})
    if not tables: raise RuntimeError(f"No {kind} table found for {season}")
    return _clean(tables[0])

def fetch_history(seasons: list[int], sleep: float=2.0) -> pd.DataFrame:
    out=[]
    for season in seasons:
        per=fetch_table(season,"per_game")
        adv=fetch_table(season,"advanced")
        poss=fetch_table(season,"per_poss")
        # Avoid duplicate common fields by keeping a curated advanced/per-100 feature set.
        adv_cols=[c for c in ["Player","Age","PER","TS%","3PAr","FTr","ORB%","DRB%","TRB%","AST%","STL%","BLK%","TOV%","USG%","WS/48","OBPM","DBPM","BPM","VORP"] if c in adv.columns]
        poss_cols=[c for c in ["Player","ORtg","DRtg"] if c in poss.columns]
        m=per.merge(adv[adv_cols], on="Player", how="left", suffixes=("","_adv")).merge(poss[poss_cols], on="Player", how="left")
        m["season"]=season; out.append(m); time.sleep(sleep)
    return pd.concat(out, ignore_index=True)
