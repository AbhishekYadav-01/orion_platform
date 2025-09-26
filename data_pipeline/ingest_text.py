# File: data_pipeline/ingest_text.py

import os
import praw
from newsapi import NewsApiClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime
from dotenv import load_dotenv
from urllib.parse import quote_plus
from datetime import datetime

# --- CONFIGURATION & SETUP ---
load_dotenv()

# Database credentials
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

# API credentials
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Tickers from the previous step
TICKERS = ["AAPL", "MSFT", "TSLA", "NVDA"]

# Database connection
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

# API Clients
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)

# --- DATABASE MODELS ---

class Stock(Base):
    __tablename__ = 'stocks'
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)

# Define the new tables for text data
class NewsArticle(Base):
    __tablename__ = 'news_articles'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, nullable=False)
    source_name = Column(String(100))
    headline = Column(String(255), nullable=False)
    content = Column(String)
    published_at = Column(DateTime, nullable=False)

class RedditPost(Base):
    __tablename__ = 'reddit_posts'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, nullable=False)
    subreddit = Column(String(100))
    title = Column(String(300), nullable=False) 
    content = Column(String)
    post_created_at = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)

# --- DATA FETCHING FUNCTIONS ---

def fetch_news(ticker, stock_id):

    print(f"Fetching news for {ticker}...")
    try:
        all_articles = newsapi.get_everything(q=ticker, language='en', sort_by='publishedAt', page_size=20)
        for article in all_articles['articles']:

            published_dt = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))

            new_article = NewsArticle(
                stock_id=stock_id,
                source_name=article['source']['name'],
                headline=article['title'],
                content=article['description'],
                published_at=published_dt
            )
            session.add(new_article)
        session.commit()
        print(f"  Saved {len(all_articles['articles'])} articles for {ticker}.")
    except Exception as e:
        print(f"  Could not fetch news for {ticker}. Error: {e}")
        session.rollback()

def fetch_reddit(ticker, stock_id):

    print(f"Fetching Reddit posts for {ticker}...")
    try:

        subreddits_to_search = "investing+stocks+wallstreetbets"
        post_count = 0
        for submission in reddit.subreddit(subreddits_to_search).search(ticker, limit=20, sort="new"):
            post_dt = datetime.fromtimestamp(submission.created_utc)
            new_post = RedditPost(
                stock_id=stock_id,
                subreddit=submission.subreddit.display_name,
                title=submission.title,
                content=submission.selftext,
                post_created_at=post_dt
            )
            session.add(new_post)
            post_count += 1
        session.commit()
        print(f"  Saved {post_count} Reddit posts for {ticker}.")
    except Exception as e:
        print(f"  Could not fetch Reddit posts for {ticker}. Error: {e}")
        session.rollback()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    for ticker in TICKERS:
        stock = session.query(Stock).filter_by(ticker=ticker).first()
        if stock:
            fetch_news(ticker, stock.id)
            fetch_reddit(ticker, stock.id)
        else:
            print(f"Stock with ticker {ticker} not found in database. Skipping.")
    
    session.close()
    print("\nText data ingestion process finished.")