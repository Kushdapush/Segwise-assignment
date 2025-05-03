import json
import time
import requests
import uuid
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import SessionLocal
from ..utils.logging import log_delivery_attempt
from datetime import timedelta

# Redis connection
redis_conn = Redis(host='redis', port=6379, db=0)
queue = Queue(connection=redis_conn)

# Retry intervals in seconds
RETRY_INTERVALS = [10, 30, 60, 300, 900]
MAX_ATTEMPTS = 5

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