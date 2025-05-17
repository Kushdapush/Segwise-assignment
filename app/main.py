import os
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from .api import subscriptions, webhooks, status
from . import models
from .database import engine, SessionLocal, get_db
from .worker.threaded import threaded_worker

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("webhook-service")

# Create database tables
models.Base.metadata.create_all(bind=engine)

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
    
    # Get worker status
    worker_status = threaded_worker.status()
    
    return {
        "status": "up",
        "database": db_status,
        "worker": worker_status
    }

@app.get("/health/worker")
def worker_health():
    """Check if worker processes are running and processing jobs."""
    return threaded_worker.status()

# Schedule periodic task to clean up old logs
@app.on_event("startup")
async def startup_event():
    from apscheduler.schedulers.background import BackgroundScheduler
    from .crud import delete_old_attempts
    
    # Start the threaded worker
    threaded_worker.start()
    logger.info("Started internal threaded worker")
    
    scheduler = BackgroundScheduler()
    
    # Schedule cleanup task every 24 hours
    @scheduler.scheduled_job('interval', hours=24)
    def cleanup_logs():
        db = SessionLocal()
        try:
            delete_old_attempts(db, hours=72)
            logger.info("Cleaned up old delivery attempt logs")
        finally:
            db.close()
    
    scheduler.start()
    logger.info("Background scheduler started for maintenance tasks")

# Graceful shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down threaded worker...")
    threaded_worker.stop()