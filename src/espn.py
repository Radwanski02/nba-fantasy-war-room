from __future__ import annotations
import json, os
from typing import Any
import requests
import pandas as pd

BASE = "https://fantasy.espn.com/apis/v3/games/fba/seasons/{season}/segments/0/leagues/{league_id}"

class ESPNClient:
    def __init__(self, league_id: int, season: int, espn_s2: str|None=None, swid: str|None=None, timeout: int=20):
        self.league_id = int(league_id); self.season = int(season); self.timeout = timeout
        self.cookies = {}
        if espn_s2 or os.getenv("ESPN_S2"): self.cookies["espn_s2"] = espn_s2 or os.getenv("ESPN_S2")
        if swid or os.getenv("SWID"): self.cookies["SWID"] = swid or os.getenv("SWID")
        self.url = BASE.format(season=self.season, league_id=self.league_id)

    def _get(self, params=None, headers=None) -> dict[str, Any]:
        r = requests.get(self.url, params=params, headers=headers, cookies=self.cookies, timeout=self.timeout)
        r.raise_for_status(); return r.json()

    def settings(self) -> dict[str, Any]:
        return self._get(params={"view":"mSettings"}).get("settings", {})

    def draft(self) -> pd.DataFrame:
        data = self._get(params={"view":"mDraftDetail"})
        picks = data.get("draftDetail", {}).get("picks", [])
        return pd.DataFrame(picks)

    def players(self, limit: int=1000) -> pd.DataFrame:
        filt = {"players":{
            "filterStatus":{"value":["FREEAGENT","WAIVERS","ONTEAM"]},
            "filterStatsForSourceIds":{"value":[0,1]},
            "filterStatsForSplitTypeIds":{"value":[0]},
            "filterRanksForScoringPeriodIds":{"value":[1]},
            "sortPercOwned":{"sortAsc":False,"sortPriority":4},
            "limit":limit,"offset":0}}
        data = self._get(params={"view":"kona_player_info"}, headers={"X-Fantasy-Filter":json.dumps(filt)})
        rows=[]
        for item in data.get("players", []):
            p = item.get("player", item.get("playerPoolEntry",{}).get("player",{}))
            ownership = p.get("ownership") or {}
            rank_obj = p.get("draftRanksByRankType") or {}
            if rank_obj:
                rank_rec = next(iter(rank_obj.values())) if isinstance(rank_obj, dict) else {}
            else: rank_rec={}
            season_proj=None
            for s in p.get("stats", []):
                if s.get("seasonId")==self.season and s.get("statTypeId")==1:
                    season_proj=s; break
            rows.append({
                "espn_id":p.get("id", item.get("id")), "player":p.get("fullName"),
                "pro_team_id":p.get("proTeamId"), "eligible_slots":p.get("eligibleSlots",[]),
                "injured":p.get("injured",False), "injury_status":p.get("injuryStatus"),
                "espn_rank":rank_rec.get("rank"), "espn_auction":rank_rec.get("auctionValue"),
                "espn_adp":ownership.get("averageDraftPosition"), "percent_owned":ownership.get("percentOwned"),
                "espn_projected_fantasy_points": (season_proj or {}).get("appliedTotal"),
                "espn_projected_stats": (season_proj or {}).get("stats",{}),
                "status":item.get("status"),
            })
        return pd.DataFrame(rows)

    @staticmethod
    def drafted_player_ids(draft_df: pd.DataFrame) -> set[int]:
        if draft_df.empty: return set()
        col = "playerId" if "playerId" in draft_df.columns else "player_id"
        return set(pd.to_numeric(draft_df.get(col, pd.Series(dtype=float)), errors="coerce").dropna().astype(int))
