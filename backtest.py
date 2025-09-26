# File: backtest.py

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus
import matplotlib.pyplot as plt

from stable_baselines3 import PPO
from rl_environment.stock_market_env import StockMarketEnv, INITIAL_CASH

# --- CONFIGURATION ---
MODEL_PATH = "ppo_stock_trader.zip"
BACKTEST_TICKER = "MSFT" # Test on a stock the agent has NOT been trained on

# --- DATABASE CONNECTION ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# --- LOAD BACKTESTING DATA ---
print(f"Loading backtesting data for {BACKTEST_TICKER}...")
sql_query = f"""
SELECT
    p.date,
    p.close,
    p.volume,
    COALESCE(AVG(n.sentiment_score), 0) AS sentiment_score
FROM stock_prices p
JOIN stocks s ON p.stock_id = s.id
LEFT JOIN news_articles n ON p.date = DATE(n.published_at) AND n.stock_id = s.id
WHERE s.ticker = '{BACKTEST_TICKER}'
GROUP BY p.date, p.close, p.volume
ORDER BY p.date;
"""
df = pd.read_sql(sql_query, engine, index_col='date')
df.dropna(inplace=True)
print(f"Loaded {len(df)} data points.")

# --- LOAD THE TRAINED MODEL ---
print(f"Loading trained model from {MODEL_PATH}...")
model = PPO.load(MODEL_PATH)

# --- SETUP THE BACKTESTING ENVIRONMENT ---
# We use the original, unwrapped environment for evaluation
eval_env = StockMarketEnv(df)

# --- RUN THE BACKTEST ---
print("\n--- Running backtest ---")
obs, info = eval_env.reset()
done = False
portfolio_values = [INITIAL_CASH]

while not done:
    # We need to manually construct the agent action dictionary
    # model.predict() will give a single action for the combined "super-agent"
    # In our simple voting environment, we can just replicate this action for all agents
    
    # Create a dictionary of observations for each agent
    # Note: In a more complex setup, you'd get individual observations
    # But our environment gives the same observation to all agents
    # For SB3, we predict on a single agent's observation
    action, _states = model.predict(obs['PULSE'], deterministic=True)
    
    # Create the action dictionary required by the PettingZoo environment
    actions = {agent: action for agent in eval_env.agents}

    # Step the environment
    obs, rewards, terminations, truncations, infos = eval_env.step(actions)
    
    # Check if the episode is done for any agent
    done = any(terminations.values()) or any(truncations.values())

    # Record portfolio value
    # We can get it from any agent's info dict
    portfolio_value = infos['PULSE']['portfolio_value']
    portfolio_values.append(portfolio_value)

print("--- Backtest complete ---")

# --- ANALYZE & DISPLAY RESULTS ---
final_portfolio_value = portfolio_values[-1]
profit = final_portfolio_value - INITIAL_CASH
return_percentage = (profit / INITIAL_CASH) * 100

print("\n--- Backtest Results ---")
print(f"Initial Portfolio Value: ${INITIAL_CASH:,.2f}")
print(f"Final Portfolio Value:   ${final_portfolio_value:,.2f}")
print(f"Total Profit/Loss:       ${profit:,.2f}")
print(f"Total Return:            {return_percentage:.2f}%")

# --- PLOT THE RESULTS ---
print("\nGenerating performance plot...")
plt.figure(figsize=(15, 6))
plt.plot(portfolio_values, label='Portfolio Value')
plt.axhline(y=INITIAL_CASH, color='r', linestyle='--', label='Initial Capital')
plt.title(f'AI Agent Performance on {BACKTEST_TICKER}')
plt.xlabel('Trading Days')
plt.ylabel('Portfolio Value ($)')
plt.legend()
plt.grid(True)
plt.show()