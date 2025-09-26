// File: frontend/dashboard/src/App.js

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Plot from 'react-plotly.js';
import './App.css';

const API_BASE_URL = 'http://127.0.0.1:8000';

function App() {
  const [tickers, setTickers] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [backtestData, setBacktestData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API_BASE_URL}/stocks`)
      .then(response => {
        setTickers(response.data.tickers);
      })
      .catch(error => {
        console.error("Error fetching tickers:", error);
        setError('Could not connect to the backend. Is the server running?');
      });
  }, []);

  const handleTickerChange = (event) => {
    const ticker = event.target.value;
    setSelectedTicker(ticker);

    if (ticker) {
      setIsLoading(true);
      setBacktestData(null);
      setError('');

      axios.get(`${API_BASE_URL}/stock/${ticker}/backtest`)
        .then(response => {
          // THE FIX IS HERE: Check if the response contains an error
          if (response.data.error) {
            setError(response.data.error);
            setBacktestData(null);
          } else {
            setBacktestData(response.data);
          }
        })
        .catch(error => {
          console.error(`Error fetching backtest for ${ticker}:`, error);
          setError(`Failed to fetch backtest results for ${ticker}.`);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setBacktestData(null);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Orion AI Trading Dashboard</h1>
      </header>
      <main>
        <div className="controls">
          <label htmlFor="ticker-select">Select a Stock Ticker:</label>
          <select id="ticker-select" value={selectedTicker} onChange={handleTickerChange}>
            <option value="">-- Please choose a ticker --</option>
            {tickers.map(ticker => (
              <option key={ticker} value={ticker}>{ticker}</option>
            ))}
          </select>
        </div>

        <div className="results">
          {isLoading && <p className="loading">Running backtest, please wait...</p>}
          {error && <p className="error">{error}</p>}
          
          {/* THE FIX IS HERE: Also check that backtestData is not null before rendering */}
          {backtestData && (
            <div id="dashboard-content">
              <h2>Backtest Results for {selectedTicker}</h2>
              <div className="stats-panel">
                <div className="stat-box">
                  <h3>Final Portfolio Value</h3>
                  <p>${backtestData.final_value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
                <div className="stat-box">
                  <h3>Total Profit/Loss</h3>
                  <p className={backtestData.profit >= 0 ? 'profit' : 'loss'}>
                    ${backtestData.profit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="stat-box">
                  <h3>Total Return</h3>
                  <p className={backtestData.return_percentage >= 0 ? 'profit' : 'loss'}>
                    {backtestData.return_percentage.toFixed(2)}%
                  </p>
                </div>
              </div>
              
              <div className="chart-container">
                <Plot
                  data={[
                    {
                      x: Array.from(Array(backtestData.portfolio_history.length).keys()),
                      y: backtestData.portfolio_history,
                      type: 'scatter',
                      mode: 'lines',
                      name: 'Portfolio Value',
                      line: { color: '#17A2B8' }
                    },
                    {
                      x: [0, backtestData.portfolio_history.length - 1],
                      y: [backtestData.initial_value, backtestData.initial_value],
                      type: 'scatter',
                      mode: 'lines',
                      name: 'Initial Capital',
                      line: { color: '#DC3545', dash: 'dash' }
                    }
                  ]}
                  layout={{
                    title: `AI Agent Performance on ${selectedTicker}`,
                    xaxis: { title: 'Trading Days' },
                    yaxis: { title: 'Portfolio Value ($)' },
                    autosize: true
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;