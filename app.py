import os, time
import pandas as pd
import streamlit as st
from src.espn import ESPNClient
from src.bref import fetch_history
from src.model import build_player_projection, rank_players
from src.live_board import available_board

LEAGUE_ID=int(os.getenv("ESPN_LEAGUE_ID","1194655201"))
SEASON=int(os.getenv("ESPN_SEASON","2027"))
st.set_page_config(page_title="NBA Fantasy Quant War Room",layout="wide")
st.title("NBA Fantasy Quant War Room")
st.caption("Live ESPN draft board + independent quant ranking")

@st.cache_data(ttl=3600*8)
def load_history(): return fetch_history([SEASON-1,SEASON-2,SEASON-3])

@st.cache_data(ttl=300)
def load_espn():
    c=ESPNClient(LEAGUE_ID,SEASON); return c.players(),c.settings()

try:
    espn,settings=load_espn(); hist=load_history()
    try: ctx=pd.read_csv("data/context_adjustments.csv",comment="#")
    except: ctx=pd.DataFrame()
    proj=build_player_projection(hist,espn,SEASON,ctx)
    ranked=rank_players(proj,settings)
    client=ESPNClient(LEAGUE_ID,SEASON); drafted=client.drafted_player_ids(client.draft())
    board=available_board(ranked,drafted,100)

    c1,c2,c3=st.columns(3)
    c1.metric("Players available",len(board)); c2.metric("Drafted",len(drafted)); c3.metric("Top pick",board.iloc[0].player if len(board) else "—")
    st.dataframe(board,use_container_width=True,hide_index=True)
    st.caption("Value Gap = ESPN ADP (or ESPN rank fallback) − Quant Rank. Positive = model says ESPN market is letting the player fall too far.")
except Exception as e:
    st.error(str(e))
    st.info("If the league is private, set ESPN_S2 and SWID in your environment. The app never needs your ESPN password.")
