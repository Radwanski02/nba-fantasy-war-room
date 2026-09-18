import os
import pandas as pd
from src.espn import ESPNClient
from src.bref import fetch_history
from src.model import build_player_projection, rank_players

league=int(os.getenv("ESPN_LEAGUE_ID","1194655201")); season=int(os.getenv("ESPN_SEASON","2027"))
c=ESPNClient(league,season)
espn=c.players(); settings=c.settings(); hist=fetch_history([season-1,season-2,season-3])
try: ctx=pd.read_csv("data/context_adjustments.csv",comment="#")
except: ctx=pd.DataFrame()
out=rank_players(build_player_projection(hist,espn,season,ctx),settings)
out.to_csv("data/draft_board.csv",index=False)
print(out[[c for c in ["model_rank","player","espn_rank","espn_adp","value_gap","market_label","quant_score","proj_games"] if c in out]].head(100).to_string(index=False))
