import os
import json
import time
import requests
import uuid
from sqlalchemy.orm import Session
from datetime import timedelta

from .. import crud, schemas
from ..database import SessionLocal
from ..utils.logging import log_delivery_attempt

# Import the threaded worker
from .threaded import enqueue_delivery

# Retry intervals in seconds
RETRY_INTERVALS = [10, 30, 60, 300, 900]
MAX_ATTEMPTS = int(os.getenv("WEBHOOK_MAX_RETRIES", "5"))

def get_cached_subscription(db, subscription_id):
    """Get a subscription from database directly (no Redis caching)."""
    subscription = crud.get_subscription(db, subscription_id=subscription_id)
    if subscription:
        subscription_data = {
            "id": str(subscription.id),
            "target_url": subscription.target_url,
            "secret": subscription.secret,
            "is_active": subscription.is_active,
            "event_types": subscription.event_types
        }
        return subscription_data
    
    return None

# Function explicitly used by API to queue a task
def queue_delivery(delivery_id: str):
    """Queue a webhook delivery using the internal thread-based worker"""
    return enqueue_delivery(delivery_id)