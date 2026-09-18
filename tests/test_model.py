import pandas as pd
from src.model import rank_players

def test_rank_points():
    df=pd.DataFrame({"player":["A","B"],"proj_PTS":[20,10],"proj_TRB":[5,5],"proj_AST":[5,5],"proj_STL":[1,1],"proj_BLK":[1,1],"proj_TOV":[2,2],"proj_3P":[2,2],"proj_games":[75,75],"history_seasons":[3,3],"Age":[27,27],"USG%":[25,20],"AST%":[25,20],"espn_adp":[10,20],"espn_rank":[10,20]})
    out=rank_players(df,{})
    assert out.iloc[0].player=="A"
