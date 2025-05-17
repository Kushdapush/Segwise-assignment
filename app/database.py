import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and "db" in DATABASE_URL:
    print("Warning: Docker database host 'db' not available when running locally.")
    print("Using SQLite database instead. For full functionality, modify DATABASE_URL.")
    DATABASE_URL = "sqlite:///./webhooks.db"

if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        print("Falling back to SQLite database")
        DATABASE_URL = "sqlite:///./webhooks.db"
        engine = create_engine(
            DATABASE_URL, connect_args={"check_same_thread": False}
        )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()