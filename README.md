# NBA Fantasy Quant War Room

A live ESPN fantasy-basketball draft engine for league `1194655201`, season `2027`.

## What it does

1. Pulls ESPN league settings so the model values players using **your league's actual scoring**, rather than generic rankings.
2. Pulls ESPN player pool data: ESPN draft rank, ADP, injuries and ESPN season projections.
3. Pulls the previous 3 NBA seasons from Basketball-Reference: per-game, per-100 and advanced statistics.
4. Produces an independent player projection using recency weighting, age curves, availability, advanced role signals and contextual adjustments.
5. Compares `Model Rank` vs `ESPN ADP / Rank` to surface values and fades.
6. Pulls ESPN draft detail to remove drafted players from the board during the live draft.

## Core model

### Historical prior
Recent seasons are weighted 55% / 30% / 15%, with a games-played reliability multiplier. The model uses both fantasy box stats and underlying metrics: USG%, AST%, STL%, BLK%, TS%, FTr, BPM, WS/48, ORtg, DRtg, per-game minutes, FGA and FTA.

### Age / development curve
Young players receive modest rate-growth priors; prime players are neutral; post-30 players receive gradual regression. This is deliberately conservative so a young-player breakout is not manufactured solely from age.

### Availability
Projected games are regressed toward a league baseline and then adjusted for age and current injury flags. Season-long value is fantasy production × expected games, not merely per-game production.

### Qualitative -> quantitative layer
Use `data/context_adjustments.csv` for evidence-backed changes that a backward-looking model cannot see yet: new team, starting-role change, recovery timeline, coach/pace shift, competition removed, etc. Each adjustment has a 0-1 confidence weight. This prevents subjective notes from overwhelming the statistical base.

Recommended interpretation:
- `minutes_delta`: change in expected minutes/game.
- `usage_delta`: decimal usage change, e.g. `0.03` = +3 percentage points.
- `games_delta`: expected games adjustment.
- `confidence`: 0 to 1 based on source quality / certainty.

### Value gap
`Value Gap = ESPN reference pick - Model Rank`.

Positive numbers mean the player is available later on ESPN than the model thinks he should be. Negative numbers mean ESPN is pricing the player earlier than the model.

## Draft-night strategy layer
The current version gives an independent best-player-available ranking. The next layer should add roster-aware marginal value: category deficits, positional scarcity, schedule/playoff-week games, correlation with your existing build, and replacement-level value at each position.

## Install / run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a
streamlit run app.py
```

Or generate a CSV:

```bash
python run_rankings.py
```

If ESPN requires authentication, add your `ESPN_S2` and `SWID` browser cookies to `.env`. Do not put them in Git.

## Draft-night output

Columns include:
- Model Rank
- Player
- ESPN Rank
- ESPN ADP
- Value Gap
- Market Label
- Quant Score
- Projected Games
- Injury Status / contextual note

The Streamlit board refreshes ESPN draft state each rerun; use Streamlit auto-rerun or refresh after picks.

## Important modeling upgrades worth adding next

- Backtest on 3-5 prior fantasy seasons: train only on information available before each season and score rank error / fantasy-value error.
- Learn feature weights with Elastic Net / Gradient Boosting rather than fixed blending.
- Add NBA.com tracking: touches, time of possession, potential assists, rebound chances, drives, catch-and-shoot attempts.
- Add lineup/on-off data to estimate role changes when teammates leave.
- Add schedule value for fantasy playoffs and games-per-week.
- Add Monte Carlo draft simulation: probability each target survives to your next pick.
- Add live roster-fit optimization after every one of your picks.
