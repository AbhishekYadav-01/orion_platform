 # File: add_stock.py

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

# Import the Stock model definition from one of our existing scripts
from data_pipeline.ingest_prices import Stock

# --- DATABASE CONNECTION ---
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def add_tickers(tickers_to_add):
    """Adds a list of tickers to the stocks table if they don't exist."""
    if not tickers_to_add:
        print("Usage: python add_stock.py <TICKER1> <TICKER2> ...")
        print("Example: python add_stock.py GOOGL AMD")
        return

    for ticker in tickers_to_add:
        ticker = ticker.upper()
        # Check if the stock already exists
        exists = session.query(Stock).filter_by(ticker=ticker).first()
        if not exists:
            new_stock = Stock(ticker=ticker, company_name=f"Company for {ticker}")
            session.add(new_stock)
            session.commit()
            print(f"✅ Added ticker '{ticker}' to the database.")
        else:
            print(f"🔹 Ticker '{ticker}' already exists. Skipping.")

    session.close()

if __name__ == "__main__":
    # Tickers are passed as command-line arguments (e.g., python add_stock.py GOOGL)
    tickers_from_args = sys.argv[1:]
    add_tickers(tickers_from_args)