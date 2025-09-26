# File: test_env.py

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

from rl_environment.stock_market_env import StockMarketEnv

# --- DATABASE CONNECTION ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# --- LOAD DATA ---
print("Loading data for AAPL...")
# A complex query to join prices with an average sentiment score per day
sql_query = """
SELECT
    p.date,
    p.close,
    p.volume,
    COALESCE(AVG(n.sentiment_score), 0) AS sentiment_score
FROM stock_prices p
JOIN stocks s ON p.stock_id = s.id
LEFT JOIN news_articles n ON p.date = DATE(n.published_at) AND n.stock_id = s.id
WHERE s.ticker = 'AAPL'
GROUP BY p.date, p.close, p.volume
ORDER BY p.date;
"""
df = pd.read_sql(sql_query, engine, index_col='date')
print(f"Loaded {len(df)} data points.")

# --- TEST THE ENVIRONMENT ---
env = StockMarketEnv(df)
observations, infos = env.reset()

print("\n--- Running test with random actions ---")
for _ in range(10): # Run for 10 steps
    # Get random actions from each agent's action space
    actions = {agent: env.action_spaces[agent].sample() for agent in env.agents}
    
    # Pass actions to the environment
    observations, rewards, terminations, truncations, infos = env.step(actions)
    
    # Print results for one agent (they are all the same in this setup)
    agent = env.possible_agents[0]
    print(f"Reward: {rewards[agent]:.2f}, Terminated: {terminations[agent]}")
    env.render()

print("\nEnvironment test complete.")