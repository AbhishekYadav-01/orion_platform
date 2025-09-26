# File: rl_environment/stock_market_env.py

import gymnasium as gym
import numpy as np
import pandas as pd
from pettingzoo import ParallelEnv

# --- CONSTANTS ---
INITIAL_CASH = 10000.0
LOOKBACK_WINDOW = 30
MAX_STEPS = 500

class StockMarketEnv(ParallelEnv):
    metadata = {"render_modes": ["human"]}

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        
        # --- THE FIX IS HERE ---
        # Explicitly set the render_mode for compatibility with wrappers
        self.render_mode = "human" 

        self.possible_agents = ["PULSE", "MOMENTUM", "GUARDIAN"]
        self.agents = self.possible_agents[:]

        self.action_spaces = {agent: gym.spaces.Discrete(3) for agent in self.agents}
        
        observation_shape = (LOOKBACK_WINDOW, 3)
        self.observation_spaces = {
            agent: gym.spaces.Box(low=-np.inf, high=np.inf, shape=observation_shape, dtype=np.float32)
            for agent in self.agents
        }
        
    def _get_observation(self, agent):
        observation_df = self.df.iloc[self.current_step - LOOKBACK_WINDOW + 1 : self.current_step + 1]
        observation = observation_df[['close', 'volume', 'sentiment_score']].values
        observation = (observation - self.df_mean) / self.df_std
        return observation.astype(np.float32)

    def reset(self, seed=None, options=None):
        self.current_step = LOOKBACK_WINDOW - 1
        self.cash = INITIAL_CASH
        self.shares_held = 0
        self.portfolio_value = INITIAL_CASH
        self.trades = []

        self.df_mean = self.df[['close', 'volume', 'sentiment_score']].mean().values
        self.df_std = self.df[['close', 'volume', 'sentiment_score']].std().values
        self.df_std[self.df_std == 0] = 1

        self.agents = self.possible_agents[:]
        
        observations = {agent: self._get_observation(agent) for agent in self.agents}
        infos = {agent: {"portfolio_value": self.portfolio_value} for agent in self.agents}
        
        return observations, infos

    def step(self, actions):
        prev_portfolio_value = self.portfolio_value

        buy_votes = sum(1 for action in actions.values() if action == 0)
        sell_votes = sum(1 for action in actions.values() if action == 1)
        
        current_price = self.df['close'].iloc[self.current_step]
        
        if buy_votes > sell_votes:
            if self.cash >= current_price:
                self.shares_held += 1
                self.cash -= current_price
                self.trades.append({'step': self.current_step, 'action': 'BUY', 'price': current_price})
        elif sell_votes > buy_votes:
            if self.shares_held > 0:
                self.shares_held -= 1
                self.cash += current_price
                self.trades.append({'step': self.current_step, 'action': 'SELL', 'price': current_price})

        self.current_step += 1
        self.portfolio_value = self.cash + (self.shares_held * self.df['close'].iloc[self.current_step])

        reward = self.portfolio_value - prev_portfolio_value
        rewards = {agent: reward for agent in self.agents}

        terminated = self.current_step >= len(self.df) - 1 or self.current_step >= MAX_STEPS
        terminations = {agent: terminated for agent in self.agents}
        truncations = {agent: False for agent in self.agents}

        observations = {agent: self._get_observation(agent) for agent in self.agents}
        infos = {agent: {"portfolio_value": self.portfolio_value} for agent in self.agents}

        if terminated:
            self.agents = []

        return observations, rewards, terminations, truncations, infos

    def render(self, mode="human"):
        profit = self.portfolio_value - INITIAL_CASH
        print(f"Step: {self.current_step}, Portfolio Value: {self.portfolio_value:.2f}, Profit: {profit:.2f}")