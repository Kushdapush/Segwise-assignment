import json
import time
import requests
import uuid
import os
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session
from datetime import timedelta

from .. import crud, schemas
from ..database import SessionLocal
from ..utils.logging import log_delivery_attempt

# Get Redis URL from environment variable
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Create more resilient Redis connections
def get_redis_connection(db=0, max_retries=3):
    """Get a Redis connection with retry logic."""
    import redis
    import time
    
    for attempt in range(max_retries):
        try:
            conn = redis.from_url(REDIS_URL, db=db)
            conn.ping()  # Test the connection
            return conn
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retrying
            else:
                raise
    
    raise Exception("Failed to connect to Redis after multiple attempts")

# Use the function to get connections
redis_client = get_redis_connection(db=0)
cache_redis = get_redis_connection(db=1)
queue = Queue(connection=redis_client)

# Retry intervals in seconds
RETRY_INTERVALS = [10, 30, 60, 300, 900]
MAX_ATTEMPTS = 5

# REMOVE THESE DUPLICATE CONNECTIONS:
# Redis connection for caching
# cache_redis = Redis.from_url(REDIS_URL, db=1)
# CACHE_TTL = 300  # 5 minutes

# Redis connection
# redis_conn = Redis.from_url(REDIS_URL, db=0)
# queue = Queue(connection=redis_conn)

# Keep this line
CACHE_TTL = 300  # 5 minutes

# Rest of the file stays the same
def get_cached_subscription(db, subscription_id):
    """Get a subscription from cache or database."""
    cache_key = f"subscription:{subscription_id}"
    
    # Try to get from cache
    cached = cache_redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)
    
    # Get from database
    subscription = crud.get_subscription(db, subscription_id=subscription_id)
    if subscription:
        # Cache the subscription
        cache_data = {
            "id": str(subscription.id),
            "target_url": subscription.target_url,
            "secret": subscription.secret,
            "is_active": subscription.is_active,
            "event_types": subscription.event_types
        }
        cache_redis.setex(
            cache_key, 
            CACHE_TTL, 
            json.dumps(cache_data)
        )
        return cache_data
    
    return None

def enqueue_delivery(delivery_id: str):
    """Enqueue a webhook delivery task."""
    queue.enqueue(deliver_webhook, delivery_id, attempt=1)

def deliver_webhook(delivery_id: str, attempt: int = 1):
    """Deliver the webhook payload to the target URL."""
    db = SessionLocal()
    try:
        # Get delivery details
        delivery = crud.get_delivery(db, delivery_id=uuid.UUID(delivery_id))
        if not delivery:
            return {"success": False, "error": "Delivery not found"}
        
        # Get subscription
        subscription = crud.get_subscription(db, subscription_id=delivery.subscription_id)
        if not subscription:
            return {"success": False, "error": "Subscription not found"}
        
        # Prepare request data
        target_url = subscription.target_url
        payload = delivery.payload
        
        # Make the HTTP request
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Delivery-ID": str(delivery.id),
                "X-Webhook-Subscription-ID": str(subscription.id)
            }
            
            if subscription.secret:
                from ..utils.security import generate_signature
                headers["X-Webhook-Signature"] = generate_signature(subscription.secret, json.dumps(payload))
            
            response = requests.post(
                target_url,
                json=payload,
                headers=headers,
                timeout=10  # 10 seconds timeout
            )
            
            # Log the attempt
            success = 200 <= response.status_code < 300
            attempt_data = schemas.DeliveryAttemptCreate(
                delivery_id=delivery.id,
                subscription_id=subscription.id,
                attempt_number=attempt,
                status_code=response.status_code,
                success=success,
                error=None if success else response.text[:255]  # Truncate if too long
            )
            crud.create_delivery_attempt(db, attempt_data)
            
            # Log to console/file
            log_delivery_attempt(
                delivery_id=delivery.id,
                subscription_id=subscription.id,
                attempt_number=attempt,
                status_code=response.status_code,
                success=success,
                error=None if success else response.text
            )
            
            # Update delivery status if successful or max attempts reached
            if success:
                crud.update_delivery_status(db, delivery_id=delivery.id, status="completed")
            elif attempt >= MAX_ATTEMPTS:
                crud.update_delivery_status(db, delivery_id=delivery.id, status="failed")
            else:
                # Schedule retry if needed
                next_attempt = attempt + 1
                if next_attempt <= MAX_ATTEMPTS:
                    delay = RETRY_INTERVALS[attempt - 1]
                    queue.enqueue_in(
                        timedelta(seconds=delay),
                        deliver_webhook,
                        delivery_id,
                        next_attempt
                    )
            
            return {
                "success": success,
                "status_code": response.status_code,
                "attempt": attempt
            }
            
        except requests.RequestException as e:
            # Log failed attempt
            attempt_data = schemas.DeliveryAttemptCreate(
                delivery_id=delivery.id,
                subscription_id=subscription.id,
                attempt_number=attempt,
                status_code=None,
                success=False,
                error=str(e)[:255]  # Truncate if too long
            )
            crud.create_delivery_attempt(db, attempt_data)
            
            # Log to console/file
            log_delivery_attempt(
                delivery_id=delivery.id,
                subscription_id=subscription.id,
                attempt_number=attempt,
                status_code=None,
                success=False,
                error=str(e)
            )
            
            # Schedule retry if not maxed out
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_INTERVALS[attempt - 1]
                queue.enqueue_in(
                    time.timedelta(seconds=delay),
                    deliver_webhook,
                    delivery_id,
                    attempt + 1
                )
            else:
                crud.update_delivery_status(db, delivery_id=delivery.id, status="failed")
                
            return {"success": False, "error": str(e), "attempt": attempt}
    
    finally:
        db.close()