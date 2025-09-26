# File: data_pipeline/ingest_prices.py

import os
import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Float, Date
from dotenv import load_dotenv
from urllib.parse import quote_plus

# --- CONFIGURATION ---
load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

TICKERS = ["AAPL", "MSFT", "TSLA", "NVDA"]

# --- DATABASE SETUP ---
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)
Base = declarative_base()

class Stock(Base):
    __tablename__ = 'stocks'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)
    company_name = Column(String(100))

class StockPrice(Base):
    __tablename__ = 'stock_prices'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# --- DATA FETCHING ---
def fetch_stock_data(symbol):
    """Fetches historical stock data from Alpha Vantage."""
    print(f"Fetching data for {symbol}...")
    url = (
        f'https://www.alphavantage.co/query?'
        f'function=TIME_SERIES_DAILY'  
        f'&symbol={symbol}'
        f'&outputsize=full'
        f'&apikey={ALPHA_VANTAGE_API_KEY}'
    )
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        if "Error Message" in data:
            print(f"  Error fetching data for {symbol}: {data['Error Message']}")
            return None
        if "Time Series (Daily)" not in data:
            print(f"  Unexpected response for {symbol}. It might be an invalid ticker or API limit.")

            return None

        df = pd.DataFrame(data['Time Series (Daily)']).T
        df.index = pd.to_datetime(df.index)
        
        df = df.rename(columns={
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume' 
        })
        
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        print(f"  Successfully fetched {len(df)} data points for {symbol}.")
        return df
    except requests.exceptions.RequestException as e:
        print(f"  HTTP Request failed: {e}")
        return None
    except Exception as e:
        print(f"  An error occurred: {e}")
        return None

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if not all([DB_PASSWORD, ALPHA_VANTAGE_API_KEY]):
        print("Error: Database password or API key is not set in the .env file.")
    else:
        for ticker in TICKERS:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                print(f"Ticker {ticker} not found in DB. Adding it.")
                stock = Stock(ticker=ticker, company_name=f"Company for {ticker}")
                session.add(stock)
                session.commit()
            
            price_df = fetch_stock_data(ticker)
            
            if price_df is not None and not price_df.empty:
                price_df['stock_id'] = stock.id
                price_df.reset_index(inplace=True)
                price_df.rename(columns={'index': 'date'}, inplace=True)
                
                print(f"  Inserting data for {ticker} into the database...")
                price_df.to_sql('stock_prices', engine, if_exists='append', index=False)
                print(f"  Data insertion for {ticker} complete.")
                
        session.close()
        print("\nData ingestion process finished.")