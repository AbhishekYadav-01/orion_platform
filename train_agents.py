# File: train_agents.py

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus

import supersuit as ss
from stable_baselines3 import PPO

from rl_environment.stock_market_env import StockMarketEnv

# --- CONFIGURATION ---
TOTAL_TIMESTEPS = 20000 # How long to train the agent. Increase for better results.
MODEL_SAVE_PATH = "ppo_stock_trader.zip"

# --- DATABASE CONNECTION ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# --- LOAD & PREPARE DATA ---
print("Loading and preparing data for training...")
# Use the same query as in the test script
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
# Drop rows with missing values that might have been created by the join
df.dropna(inplace=True)
print(f"Loaded {len(df)} data points.")

# --- ENVIRONMENT SETUP ---
# 1. Create the PettingZoo environment
env = StockMarketEnv(df)

# 2. Wrap the environment to make it compatible with Stable Baselines3
# This is a crucial step from the SuperSuit library
env = ss.pettingzoo_env_to_vec_env_v1(env)

# 3. Stack observations to give the agent a sense of momentum
# It will see the current and the last 3 observations
env = ss.concat_vec_envs_v1(env, 4, num_cpus=1, base_class='stable_baselines3')

# --- MODEL TRAINING ---
# We'll use the Proximal Policy Optimization (PPO) algorithm
# 'MlpPolicy' means the agent uses a simple neural network
model = PPO('MlpPolicy', env, verbose=1)

print("\n--- Starting model training ---")
# This is where the magic happens! The agent learns by interacting with the env.
model.learn(total_timesteps=TOTAL_TIMESTEPS)
print("--- Training complete ---")

# --- SAVE THE TRAINED MODEL ---
print(f"Saving trained model to {MODEL_SAVE_PATH}...")
model.save(MODEL_SAVE_PATH)
print("Model saved successfully.")