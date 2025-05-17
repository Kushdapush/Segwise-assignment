import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from rq import Queue
from .api import subscriptions, webhooks, status
from . import models
from .database import engine, SessionLocal, get_db
from .worker.combined import combined_worker
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

@app.get("/health/worker")
def worker_health_check():
    """Check if worker processes are running and processing jobs."""
    try:
        # Check if workers are active
        workers = Queue(connection=redis_client).workers
        worker_count = len(workers)
        
        # Check queue statistics
        queue = Queue(connection=redis_client)
        queue_length = len(queue)
        
        return {
            "status": "healthy" if worker_count > 0 else "unhealthy",
            "workers": worker_count,
            "queue_size": queue_length
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.on_event("startup")
async def startup_event():
    # Start the combined worker
    combined_worker.start()
    
    # Your existing scheduler code
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

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the combined worker
    combined_worker.stop()

@app.get("/health/internal-worker")
def internal_worker_health():
    """Get status of the internal worker thread."""
    status = combined_worker.status()
    
    # Also check if Redis is accessible directly
    redis_status = "unknown"
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "internal_worker": status,
        "redis_direct": redis_status
    }