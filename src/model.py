from __future__ import annotations
import math
import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

BOX = ["PTS","TRB","AST","STL","BLK","TOV","3P","FG%","FT%"]
RATE_FEATURES=["PTS","TRB","AST","STL","BLK","TOV","3P","USG%","AST%","STL%","BLK%","TS%","FTr","BPM","WS/48","ORtg","DRtg"]

def weighted_history(hist: pd.DataFrame, target_season: int, weights=(0.55,0.30,0.15)) -> pd.DataFrame:
    seasons=[target_season-1,target_season-2,target_season-3]
    parts=[]
    for s,w in zip(seasons,weights):
        x=hist[hist.season==s].copy(); x["w"]=w
        # Numeric coercion
        for c in x.columns:
            if c not in ["Player","Team","Pos","Awards"]: x[c]=pd.to_numeric(x[c],errors="coerce")
        parts.append(x)
    z=pd.concat(parts,ignore_index=True)
    rows=[]
    for player,g in z.groupby("Player"):
        rec={"player":player}
        ww=g["w"] * np.clip(g.get("G",82).fillna(0)/65,0.25,1.0)
        for c in RATE_FEATURES+["MP","G","Age","FGA","FTA","FG%","FT%"]:
            if c in g:
                valid=g[c].notna(); denom=ww[valid].sum()
                rec[c]=(g.loc[valid,c]*ww[valid]).sum()/denom if denom else np.nan
        rec["history_seasons"]=g.season.nunique(); rows.append(rec)
    return pd.DataFrame(rows)

def age_multiplier(age: float) -> float:
    if pd.isna(age): return 1.0
    # Mild growth through 24, plateau 25-29, gradual decline after 30.
    if age <= 21: return 1.06
    if age <= 24: return 1.03
    if age <= 29: return 1.00
    if age <= 32: return 0.985 ** (age-29)
    return 0.955 ** (age-32) * (0.985**3)

def project_games(games: float, age: float, injured=False) -> float:
    base=72 if pd.isna(games) else 0.60*games + 0.40*74
    if age and age>31: base -= min(8,(age-31)*1.3)
    if injured: base -= 5
    return float(np.clip(base, 45, 82))

def apply_context(df: pd.DataFrame, context: pd.DataFrame|None) -> pd.DataFrame:
    out=df.copy()
    if context is None or context.empty: return out
    ctx=context.copy(); ctx=ctx[~ctx["player"].astype(str).str.startswith("#")]
    ctx["confidence"]=pd.to_numeric(ctx.get("confidence",0),errors="coerce").fillna(0).clip(0,1)
    out=out.merge(ctx[["player","minutes_delta","usage_delta","games_delta","confidence","reason"]],on="player",how="left")
    for c in ["minutes_delta","usage_delta","games_delta","confidence"]: out[c]=pd.to_numeric(out[c],errors="coerce").fillna(0)
    out["proj_mp"] += out.minutes_delta*out.confidence
    if "USG%" in out: out["USG%"] += out.usage_delta*out.confidence*100
    out["proj_games"] += out.games_delta*out.confidence
    return out

def build_player_projection(hist: pd.DataFrame, espn: pd.DataFrame, target_season: int, context=None) -> pd.DataFrame:
    base=weighted_history(hist,target_season)
    base["proj_mp"]=base["MP"].fillna(24).clip(8,39)
    base["proj_games"]=[project_games(g,a,False) for g,a in zip(base.get("G",72),base.get("Age",27))]
    # Box-score projection: age-adjust recent weighted per-game rates; minutes change handled proportionally.
    am=base.get("Age",27).apply(age_multiplier)
    for c in ["PTS","TRB","AST","STL","BLK","TOV","3P"]:
        if c in base: base[f"proj_{c}"]=base[c]*am
    base=apply_context(base,context)

    # Match ESPN names robustly.
    if espn is not None and not espn.empty:
        choices=espn.player.dropna().tolist(); mp={}
        for name in base.player:
            best=process.extractOne(name,choices,scorer=fuzz.WRatio,score_cutoff=88)
            if best: mp[name]=best[0]
        base["espn_name"]=base.player.map(mp)
        base=base.merge(espn,left_on="espn_name",right_on="player",how="left",suffixes=("","_espn"))
        base["player"]=base["player"]
    return base

def parse_scoring(settings: dict) -> tuple[str, dict]:
    """Return ('points'|'categories', scoring map). ESPN schemas vary, so this is defensive."""
    s=settings.get("scoringSettings",settings.get("scoring",{})) if settings else {}
    st=str(s.get("scoringType", settings.get("scoringType", ""))).upper()
    mode="categories" if "CATEGORY" in st or "H2H_CATEGORY" in st else "points"
    items={}
    for item in s.get("scoringItems",[]):
        stat_id=str(item.get("statId")); pts=item.get("points", item.get("pointsOverride", item.get("value",0)))
        try: items[stat_id]=float(pts)
        except: pass
    return mode,items

# Common ESPN NBA stat ids frequently seen in league settings. Settings remain source of truth.
ESPN_STAT_TO_COL={"0":"PTS","1":"BLK","2":"STL","3":"AST","6":"TRB","11":"TOV","17":"3P"}

def points_value(df: pd.DataFrame, scoring: dict) -> pd.Series:
    if not scoring:
        # Sensible fallback, only used if league settings fail to expose weights.
        scoring={"0":1,"1":4,"2":4,"3":2,"6":1,"11":-1,"17":1}
    total=pd.Series(0.0,index=df.index)
    used=0
    for sid,w in scoring.items():
        col=ESPN_STAT_TO_COL.get(str(sid))
        pcol=f"proj_{col}" if col else None
        if pcol in df: total += df[pcol].fillna(0)*w; used+=1
    if used==0:
        total = df.get("proj_PTS",0)+1.2*df.get("proj_TRB",0)+1.5*df.get("proj_AST",0)+3*df.get("proj_STL",0)+3*df.get("proj_BLK",0)-df.get("proj_TOV",0)
    return total*df["proj_games"]

def category_value(df: pd.DataFrame) -> pd.Series:
    cols=[c for c in ["proj_PTS","proj_TRB","proj_AST","proj_STL","proj_BLK","proj_3P"] if c in df]
    z=pd.DataFrame(index=df.index)
    for c in cols:
        sd=df[c].std(ddof=0) or 1; z[c]=(df[c]-df[c].mean())/sd
    # Turnovers inverted. Percentages are intentionally handled as efficiency confidence penalties/bonuses below.
    if "proj_TOV" in df:
        sd=df.proj_TOV.std(ddof=0) or 1; z["TOV"]=(df.proj_TOV.mean()-df.proj_TOV)/sd
    if "FG%" in df:
        impact=(df["FG%"]-df["FG%"].mean())/(df["FG%"].std(ddof=0) or 1)
        z["FG%"] = impact*np.sqrt(df.get("FGA",8).clip(lower=1)/df.get("FGA",8).median())
    if "FT%" in df:
        impact=(df["FT%"]-df["FT%"].mean())/(df["FT%"].std(ddof=0) or 1)
        z["FT%"] = impact*np.sqrt(df.get("FTA",3).clip(lower=1)/df.get("FTA",3).median())
    return z.sum(axis=1)

def rank_players(df: pd.DataFrame, settings: dict|None=None, roster_needs: dict|None=None) -> pd.DataFrame:
    out=df.copy(); mode,scoring=parse_scoring(settings or {})
    out["raw_value"] = points_value(out,scoring) if mode=="points" else category_value(out)
    # Reliability: history, projected games, and stable advanced contribution.
    out["reliability"]=(out.history_seasons.clip(0,3)/3*0.45 + out.proj_games.clip(45,82)/82*0.55)
    # Upside proxy: youth + underlying role strength (usage/assist rates) vs current production.
    youth=np.clip((28-out.get("Age",28))/10,-0.3,0.7)
    role=(out.get("USG%",20).fillna(20)-20)/25 + (out.get("AST%",15).fillna(15)-15)/50
    out["upside"]=(youth+role).clip(-0.5,1.0)
    out["quant_score"]=out.raw_value*(0.90+0.10*out.reliability)*(1+0.08*out.upside)
    out["model_rank"]=out.quant_score.rank(method="min",ascending=False).astype(int)
    out["espn_reference_pick"]=out.espn_adp.fillna(out.espn_rank) if "espn_adp" in out else np.nan
    out["value_gap"]=out.espn_reference_pick-out.model_rank
    out["market_label"]=np.select([out.value_gap>=12,out.value_gap>=5,out.value_gap<=-12,out.value_gap<=-5],["Strong value","Value","Strong fade","Fade"],default="Fair")
    return out.sort_values(["model_rank","espn_reference_pick"],na_position="last")
