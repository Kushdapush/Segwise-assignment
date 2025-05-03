import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from .api import subscriptions, webhooks, status
from . import models
from .database import engine, SessionLocal, get_db
import redis

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Setup Redis connection for caching
REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL)

app = FastAPI(
    title="Webhook Delivery Service",
    description="A service for receiving, queueing, and delivering webhooks",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(status.router, prefix="/status", tags=["status"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Webhook Delivery Service"}

@app.get("/health")
def health_check():
    # Check database connection
    db = SessionLocal()
    try:
        # Import text from sqlalchemy
        from sqlalchemy import text
        
        # Execute simple query to check DB connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    finally:
        db.close()
    
    # Check Redis connection
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "up",
        "database": db_status,
        "redis": redis_status
    }

# Schedule periodic task to clean up old logs
@app.on_event("startup")
async def startup_event():
    from apscheduler.schedulers.background import BackgroundScheduler
    from .crud import delete_old_attempts
    
    scheduler = BackgroundScheduler()
    
    # Schedule cleanup task every 24 hours
    @scheduler.scheduled_job('interval', hours=24)
    def cleanup_logs():
        db = SessionLocal()
        try:
            delete_old_attempts(db, hours=72)
        finally:
            db.close()
    
    scheduler.start()