import pandas as pd
from sqlalchemy import create_engine, text
from .config import DB_URL

engine = create_engine(DB_URL, pool_pre_ping=True)

def query_df(sql: str, **params) -> pd.DataFrame:
    with engine.connect() as c:
        return pd.read_sql(text(sql), c, params=params)
