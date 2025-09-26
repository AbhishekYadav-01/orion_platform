# File: backend/main.py

import os
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text # <-- IMPORT text
from dotenv import load_dotenv
from urllib.parse import quote_plus
import matplotlib
matplotlib.use('Agg')

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stable_baselines3 import PPO
from rl_environment.stock_market_env import StockMarketEnv, INITIAL_CASH

# --- APP INITIALIZATION & CORS ---

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE & MODEL LOADING ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

MODEL_PATH = os.path.join("..", "ppo_stock_trader.zip")
model = PPO.load(MODEL_PATH)
print("AI model loaded successfully.")

# --- HELPER FUNCTIONS ---

def load_stock_data(ticker: str):
    sql_query = f"""
    SELECT
        p.date,
        p.close,
        p.volume,
        COALESCE(AVG(n.sentiment_score), 0) AS sentiment_score
    FROM stock_prices p
    JOIN stocks s ON p.stock_id = s.id
    LEFT JOIN news_articles n ON p.date = DATE(n.published_at) AND n.stock_id = s.id
    WHERE s.ticker = '{ticker.upper()}'
    GROUP BY p.date, p.close, p.volume
    ORDER BY p.date;
    """
    df = pd.read_sql(sql_query, engine, index_col='date')
    df.dropna(inplace=True)
    return df

def run_backtest_for_ticker(df: pd.DataFrame):
    eval_env = StockMarketEnv(df)
    obs, info = eval_env.reset()
    done = False
    portfolio_values = [INITIAL_CASH]

    while not done:
        action, _states = model.predict(obs['PULSE'], deterministic=True)
        actions = {agent: action for agent in eval_env.agents}
        obs, rewards, terminations, truncations, infos = eval_env.step(actions)
        done = any(terminations.values()) or any(truncations.values())
        portfolio_values.append(infos['PULSE']['portfolio_value'])

    final_value = portfolio_values[-1]
    profit = final_value - INITIAL_CASH
    return_pct = (profit / INITIAL_CASH) * 100

    return {
        "initial_value": INITIAL_CASH,
        "final_value": final_value,
        "profit": profit,
        "return_percentage": return_pct,
        "portfolio_history": portfolio_values
    }

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "Orion Platform API is running."}

@app.get("/stocks")
def get_stocks():
    """Returns a list of all available stock tickers."""
    with engine.connect() as connection:
        # --- THE FIX IS HERE ---
        # Wrap the raw SQL string in the text() construct
        query = text("SELECT ticker FROM stocks ORDER BY ticker;")
        result = connection.execute(query)
        tickers = [row[0] for row in result]
    return {"tickers": tickers}

@app.get("/stock/{ticker}/data")
def get_stock_data(ticker: str):
    df = load_stock_data(ticker)
    df_reset = df.reset_index()
    return df_reset.to_dict(orient='records')

@app.get("/stock/{ticker}/backtest")
def get_backtest_results(ticker: str):
    print(f"Running backtest for {ticker}...")
    df = load_stock_data(ticker)
    if len(df) < 60:
        return {"error": "Not enough data to run a backtest for this ticker."}
    
    results = run_backtest_for_ticker(df)
    print(f"Backtest for {ticker} complete. Final value: {results['final_value']:.2f}")
    return results