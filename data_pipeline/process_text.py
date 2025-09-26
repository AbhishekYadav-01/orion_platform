# File: data_pipeline/process_text.py

import os
import torch
from sqlalchemy import create_engine, Column, Float, inspect, text 
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from tqdm import tqdm

from ingest_text import NewsArticle, RedditPost

# --- CONFIGURATION & SETUP ---
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

NewsArticle.sentiment_score = Column(Float)
RedditPost.sentiment_score = Column(Float)

# --- AI MODEL LOADING ---
print("Loading FinBERT model and tokenizer...")
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
print("Model loaded successfully.")

# --- SENTIMENT ANALYSIS FUNCTION ---
def get_sentiment(text):
    if not text or not isinstance(text, str):
        return 0.0

    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs).logits
        
        scores = torch.nn.functional.softmax(logits, dim=1)[0]
        
        positive_prob = scores[0].item()
        negative_prob = scores[1].item()
        
        sentiment_score = positive_prob - negative_prob
        return sentiment_score
    except Exception as e:
        print(f"  Error processing text: {text[:50]}... | Error: {e}")
        return 0.0

# --- THE FIX IS IN THIS FUNCTION ---
def add_sentiment_column_if_not_exists(table_name):
    """Checks if the sentiment_score column exists and adds it if it doesn't."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    if 'sentiment_score' not in columns:
        print(f"Adding 'sentiment_score' column to '{table_name}' table.")
        with engine.connect() as connection:
            # Wrap the raw SQL string in the text() construct
            command = text(f'ALTER TABLE {table_name} ADD COLUMN sentiment_score FLOAT;')
            connection.execute(command)
            connection.commit()
        print("Column added.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    add_sentiment_column_if_not_exists('news_articles')
    add_sentiment_column_if_not_exists('reddit_posts')

    articles_to_process = session.query(NewsArticle).filter(NewsArticle.sentiment_score == None).all()
    print(f"\nFound {len(articles_to_process)} news articles to analyze.")
    for article in tqdm(articles_to_process, desc="Analyzing News"):
        article.sentiment_score = get_sentiment(article.headline)
    session.commit()
    print("News analysis complete.")

    posts_to_process = session.query(RedditPost).filter(RedditPost.sentiment_score == None).all()
    print(f"\nFound {len(posts_to_process)} Reddit posts to analyze.")
    for post in tqdm(posts_to_process, desc="Analyzing Reddit"):
        post.sentiment_score = get_sentiment(post.title)
    session.commit()
    print("Reddit analysis complete.")

    session.close()
    print("\nText processing finished.")