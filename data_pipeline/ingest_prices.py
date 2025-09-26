# File: data_pipeline/ingest_prices.py

import os
import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Float, Date
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
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

def fetch_stock_data(symbol):
    print(f"Fetching data for {symbol}...")
    url = (
        f'https://www.alphavantage.co/query?'
        f'function=TIME_SERIES_DAILY'
        f'&symbol={symbol}'
        f'&outputsize=full'
        f'&apikey={ALPHA_VANTAGE_API_KEY}'
    )
    # ... (rest of the function is identical)
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        if "Error Message" in data or "Information" in data or "Note" in data:
            print(f"  API Error/Limit for {symbol}: {data}")
            return None
        if "Time Series (Daily)" not in data:
            print(f"  Unexpected response for {symbol}.")
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

if __name__ == "__main__":
    # --- THIS IS THE MAIN CHANGE ---
    # Fetch all tickers directly from the database
    all_stocks = session.query(Stock).all()
    TICKERS = [stock.ticker for stock in all_stocks]
    print(f"Found tickers in DB: {TICKERS}")

    for ticker in TICKERS:
        stock = session.query(Stock).filter_by(ticker=ticker).first()
        price_df = fetch_stock_data(ticker)
        
        if price_df is not None and not price_df.empty:
            price_df['stock_id'] = stock.id
            price_df.reset_index(inplace=True)
            price_df.rename(columns={'index': 'date'}, inplace=True)
            
            print(f"  Inserting data for {ticker} into the database...")
            price_df.to_sql('stock_prices', engine, if_exists='append', index=False, chunksize=1000)
            print(f"  Data insertion for {ticker} complete.")
            
    session.close()
    print("\nData ingestion process finished.")